import asyncio
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Any, Optional
from playwright.async_api import async_playwright

from scrapewizard.core.logging import log
from scrapewizard.engine.checks import ConsoleNetworkTracker, perform_visual_check, perform_a11y_check
from scrapewizard.engine.healing import attempt_self_healing

@dataclass
class StepResult:
    step_name: str
    status: str  # "passed" | "failed" | "error"
    duration_ms: int
    screenshot_path: Optional[str]
    visual_diff_score: Optional[float]
    console_errors: List[str]
    network_errors: List[str]
    a11y_violations: List[dict]
    healed: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class RunResult:
    status: str  # "passed" | "failed" | "error"
    step_results: List[StepResult]
    duration_ms: int
    artifacts_dir: str
    ai_calls: int = 0
    ai_cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "step_results": [r.to_dict() for r in self.step_results],
            "duration_ms": self.duration_ms,
            "artifacts_dir": self.artifacts_dir,
            "ai_calls": self.ai_calls,
            "ai_cost_usd": self.ai_cost_usd
        }

async def resolve_element(page, selectors: List[Dict[str, Any]]):
    """Try resolving an element from its selector ladder in rank order."""
    for s in selectors:
        try:
            if s["kind"] == "css":
                loc = page.locator(s["value"])
            else:
                loc = page.locator(f"xpath={s['value']}")
            
            if await loc.count() > 0:
                # Wait briefly for stability
                await loc.first.wait_for(state="attached", timeout=2000)
                return loc.first
        except Exception:
            continue
    return None

class SandboxRunner:
    """
    Isolated test runner that executes generated steps and tracks visual, console,
    network, and accessibility status quality signals.
    """
    def __init__(
        self,
        artifacts_dir: Optional[str] = None,
        baselines_dir: Optional[str] = None,
        flow_name: str = "default",
        headless: bool = True,
    ):
        self.headless = headless
        
        # Setup per-run artifacts directory (screenshots, diffs, reports)
        if artifacts_dir:
            self.artifacts_dir = Path(artifacts_dir)
        else:
            timestamp = int(time.time())
            self.artifacts_dir = Path("runs") / f"run_{timestamp}"
            
        self.screenshots_dir = self.artifacts_dir / "screenshots"
        self.diffs_dir = self.artifacts_dir / "diffs"

        # Baselines live in a STABLE shared location, NOT under the per-run
        # artifacts dir. This ensures successive runs compare against the same
        # baseline images instead of re-baselining every execution.
        if baselines_dir:
            self.baselines_dir = Path(baselines_dir)
        else:
            self.baselines_dir = (
                Path.home() / ".scrapewizard" / "baselines" / flow_name
            )

        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.baselines_dir.mkdir(parents=True, exist_ok=True)
        self.diffs_dir.mkdir(parents=True, exist_ok=True)

    async def run(self, test_def: Dict[str, Any]) -> RunResult:
        start_time = time.time()
        step_results = []
        overall_status = "passed"
        
        steps = test_def.get("steps", [])
        
        async with async_playwright() as p:
            # Launch fresh context
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            page = await context.new_page()
            
            # Setup console & network tracker
            tracker = ConsoleNetworkTracker(page)
            
            for step in steps:
                step_name = step.get("name", "step")
                action = step.get("action")
                value = step.get("value")
                selectors = step.get("selectors", [])
                
                step_start = time.time()
                status = "passed"
                healed = False
                error_msg = None
                
                log(f"Sandbox executing step: {step_name} ({action})")
                
                try:
                    # Execute action
                    if action == "navigate":
                        await page.goto(value)
                    elif action == "click":
                        el = await resolve_element(page, selectors)
                        if not el:
                            # Attempt self-healing
                            el = await attempt_self_healing(page, step.get("fingerprint"))
                            if not el:
                                raise Exception(f"Failed to resolve element for click using ladder and self-healing: {selectors}")
                            healed = True
                        await el.click()
                    elif action == "fill":
                        el = await resolve_element(page, selectors)
                        if not el:
                            # Attempt self-healing
                            el = await attempt_self_healing(page, step.get("fingerprint"))
                            if not el:
                                raise Exception(f"Failed to resolve element for fill using ladder and self-healing: {selectors}")
                            healed = True
                        await el.fill(value)
                    else:
                        raise Exception(f"Unsupported action: {action}")
                        
                    # Process assertions
                    for assertion in step.get("assertions", []):
                        kind = assertion.get("kind")
                        expected = assertion.get("value")
                        if kind == "url":
                            try:
                                await page.wait_for_url(expected, timeout=3000)
                            except Exception:
                                pass
                            assert page.url.rstrip("/") == expected.rstrip("/"), f"Expected URL: {expected}, got: {page.url}"
                        elif kind == "visible":
                            # Resolve target or check assertion value as CSS
                            target_selectors = selectors if selectors else [{"kind": "css", "value": expected}]
                            el = await resolve_element(page, target_selectors)
                            if not el:
                                # Attempt self-healing for visible assertion
                                el = await attempt_self_healing(page, step.get("fingerprint"))
                                if not el:
                                    raise AssertionError(f"Assertion failed: element {expected} is not visible and could not be healed")
                                healed = True
                            assert await el.is_visible(), f"Assertion failed: element {expected} is not visible"

                except Exception as e:
                    status = "failed"
                    overall_status = "failed"
                    error_msg = str(e)
                    log(f"Step {step_name} failed: {e}", level="error")
                
                # Capture screenshot
                screenshot_path = self.screenshots_dir / f"{step_name}.png"
                try:
                    await page.screenshot(path=str(screenshot_path))
                    screenshot_str = str(screenshot_path)
                except Exception:
                    screenshot_str = None
                    
                # Run console/network checks
                console_errors, network_errors = tracker.flush()
                
                # Run visual comparison check
                visual_diff_score = None
                if screenshot_str:
                    visual_diff_score, _ = perform_visual_check(
                        screenshot_str,
                        step_name,
                        str(self.baselines_dir),
                        str(self.diffs_dir)
                    )
                    
                # Run accessibility check
                a11y_violations = await perform_a11y_check(page)
                
                step_end = time.time()
                duration_ms = int((step_end - step_start) * 1000)
                
                step_results.append(StepResult(
                    step_name=step_name,
                    status=status,
                    duration_ms=duration_ms,
                    screenshot_path=screenshot_str,
                    visual_diff_score=visual_diff_score,
                    console_errors=console_errors,
                    network_errors=network_errors,
                    a11y_violations=a11y_violations,
                    healed=healed,
                    error_message=error_msg
                ))
                
                # If step failed, abort remaining steps
                if status == "failed":
                    break
                    
            await context.close()
            await browser.close()
            
        end_time = time.time()
        duration_ms = int((end_time - start_time) * 1000)
        
        return RunResult(
            status=overall_status,
            step_results=step_results,
            duration_ms=duration_ms,
            artifacts_dir=str(self.artifacts_dir)
        )
