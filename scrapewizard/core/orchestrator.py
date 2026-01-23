import json
import asyncio
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.console import Console
from rich.panel import Panel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from scrapewizard.core.state import State
from scrapewizard.core.project_manager import ProjectManager
from scrapewizard.core.logging import log
from scrapewizard.core.config import ConfigManager
from scrapewizard.core.constants import (
    STATE_EMOJIS, 
    DEFAULT_SCRIPT_TIMEOUT, 
    LLM_CONFIDENCE_THRESHOLD,
    SCAN_NAVIGATION_TIMEOUT,
    PROBE_NAVIGATION_TIMEOUT
)
from scrapewizard.utils.file_io import safe_read_json, safe_write_json

from scrapewizard.interactive.ui import UI
from scrapewizard.utils.ux import UX
from scrapewizard.recon.browser import BrowserManager
from scrapewizard.recon.scanner import Scanner
from scrapewizard.recon.dom_analyzer import DOMAnalyzer
from scrapewizard.recon.pagination import PaginationDetector
from scrapewizard.recon.tech_fingerprint import TechFingerprinter

from scrapewizard.llm.understanding import UnderstandingAgent
from scrapewizard.llm.codegen import CodeGenerator
from scrapewizard.llm.repair import RepairAgent

from scrapewizard.healing.repair_loop import RepairLoop
from scrapewizard.runtime.tester import ScriptTester

class Orchestrator:
    """
    Main controller for the scraping workflow.
    Uses synchronous flow with isolated async blocks for browser operations.
    """

    def __init__(self, project_dir: Path, ci_mode: bool = False, wizard_mode: bool = True, guided_tour: bool = False, interactive_mode: bool = False):
        self.project_dir = Path(project_dir)
        self.ci_mode = ci_mode
        self.wizard_mode = wizard_mode  # Default: Zero-Click logic
        self.interactive_mode = interactive_mode # "One Smart Question" logic
        self.guided_tour = guided_tour
        self._working_shown = False  # Track working message
        self.session = ProjectManager.load_project(str(self.project_dir))
        if not self.session:
            raise ValueError(f"Invalid project directory: {project_dir}")
        self.start_time = time.time()
        
    def _emit_wide_event(self, success: bool, error: Optional[str] = None) -> None:
        """Emit a 'Wide Event' JSON with full session metadata."""
        try:
            duration = time.time() - self.start_time
            wide_event = {
                "event_type": "session_completion",
                "project_id": self.session.get("project_id"),
                "url": self.session.get("url"),
                "success": success,
                "duration_seconds": round(duration, 2),
                "error": error,
                "wizard_mode": self.wizard_mode,
                "ci_mode": self.ci_mode,
                "guided_tour": self.guided_tour,
                "final_state": self.session.get("state"),
                "timestamp": datetime.now().isoformat()
            }
            safe_write_json(self.project_dir / "wide_event.json", wide_event)
            log("Wide event emitted", level="debug", **wide_event)
        except Exception as e:
            log(f"Failed to emit wide event: {e}", level="warning")

    def run(self) -> None:
        """Main execution loop (synchronous)."""
        success = False
        error_msg = None
        try:
            self._run_internal()
            success = self.session["state"] == State.DONE.value
        except Exception as e:
            error_msg = str(e)
            log(f"Fatal error in orchestrator: {traceback.format_exc()}", level="critical")
            raise
        finally:
            self._emit_wide_event(success, error_msg)

    def _narrate(self, message: str, delay: float = 1.0) -> None:
        """Narrate steps in Guided Tour mode.
        
        Args:
            message: The message to narrate.
            delay: Delay in seconds after narration.
        """
        if self.guided_tour:
            Console().print(f"\n[bold magenta]🧙 Guide:[/bold magenta] {message}")
            time.sleep(delay)
            input("\n[dim]Press Enter to continue...[/dim]")

    def _progress_step(self, step_num: int, label: str, duration: float = 1.0) -> None:
        """Displays a progress bar for a workflow step in Wizard Mode.
        
        Args:
            step_num: The index of the current step.
            label: Descriptive name of the step.
            duration: Simulated duration for the progress bar animation.
        """
        if not self.wizard_mode:
            return
        
        # Determine emoji based on common step labels
        emoji = "✨"
        if "Opening" in label: emoji = STATE_EMOJIS["INIT"]
        elif "Understanding" in label: emoji = STATE_EMOJIS["RECON"]
        elif "Analyzing" in label: emoji = STATE_EMOJIS["LLM_ANALYSIS"]
        elif "Selecting" in label: emoji = STATE_EMOJIS["USER_CONFIG"]
        elif "Writing" in label: emoji = STATE_EMOJIS["CODEGEN"]
        elif "Testing" in label: emoji = STATE_EMOJIS["TEST"]
        elif "Repairing" in label: emoji = STATE_EMOJIS["REPAIR"]
        elif "Final" in label: emoji = STATE_EMOJIS["FINAL_RUN"]

        with Progress(
            SpinnerColumn(),
            TextColumn(f"{emoji} [bold blue]Step {step_num}/6:[/bold blue] {label}"),
            BarColumn(),
            TimeElapsedColumn(),
            transient=True
        ) as progress:
            task = progress.add_task("working", total=100)
            for _ in range(10):
                time.sleep(duration / 10)
                progress.update(task, advance=10)

    def _run_internal(self) -> None:
        """Internal execution loop logic."""
        if self.guided_tour:
            Console().print(Panel.fit(
                "[bold cyan]Welcome to the ScrapeWizard Guided Tour![/bold cyan]\n"
                "I'll walk you through how I build a professional scraper step-by-step.",
                title="🧙 Tour"
            ))

        if not self.wizard_mode:
            log("Starting Orchestrator loop...")
            if self.ci_mode:
                log("CI Mode enabled: Automatic defaults will be used.")
            
        while self.session["state"] != State.DONE.value and self.session["state"] != State.FAILED.value:
            current_state = self.session["state"]
            if not self.wizard_mode:
                log(f"Current State: {current_state}")
            
            try:
                if current_state == State.INIT.value:
                    self._handle_init()
                elif current_state == State.LOGIN.value or current_state == State.GUIDED_ACCESS.value:
                    self._handle_guided_access()
                elif current_state == State.RECON.value:
                    self._handle_recon()
                elif current_state == State.LLM_ANALYSIS.value:
                    self._handle_llm_analysis()
                elif current_state == State.USER_CONFIG.value:
                    self._handle_user_config()
                elif current_state == State.CODEGEN.value:
                    self._handle_codegen()
                elif current_state == State.TEST.value:
                    self._handle_test()
                elif current_state == State.REPAIR.value:
                    self._handle_repair()
                elif current_state == State.INTERACTIVE_SOLVE.value:
                    self._handle_interactive_solve()
                elif current_state == State.APPROVED.value:
                    self._handle_final_run()
                else:
                    log(f"State {current_state} not handled.", level="error")
                    self._transition_to(State.FAILED)
                    break
                    
                ProjectManager.save_state(self.project_dir, self.session)
                
            except KeyboardInterrupt:
                log("Operation cancelled by user.", level="warning")
                self._transition_to(State.FAILED)
                break
            except Exception:
                log(f"Critical execution error: {traceback.format_exc()}", level="error")
                self._transition_to(State.FAILED)
                ProjectManager.save_state(self.project_dir, self.session)
                raise

    def _transition_to(self, new_state: State):
        if not self.wizard_mode:
            log(f"Transitioning: {self.session['state']} -> {new_state.value}")
        self.session["state"] = new_state.value

    def _handle_init(self) -> None:
        """Step 1: Analyze complexity -> Ask Access Mode."""
        self._progress_step(1, "Opening site", duration=2.0)
        self._narrate("I'm starting a brief 'Stealth Probe' to see how the website reacts to automation.")

        # Wizard mode: Show friendly welcome
        if self.wizard_mode:
            print("\n🧙 ScrapeWizard\n")
        
        if self.ci_mode:
            log("CI Mode: Skipping complexity check, defaulting to Automatic.")
            self._transition_to(State.RECON)
            return

        # 1. Run Pre-Scan in Stealth Probe mode (headed, not guided)
        if not self.wizard_mode:
            log("Running Pre-Scan to determine site complexity...")
        
        # Pre-Scan uses HEADED mode to trigger real bot defenses (Akamai, PerimeterX, etc.)
        # This is a silent probe - no user interaction required
        @retry(
            wait=wait_exponential(multiplier=1, min=2, max=10),
            stop=stop_after_attempt(3),
            retry=retry_if_exception_type((Exception)), # Broad for network/playwright issues
            reraise=True
        )
        async def do_prescan():
            browser = BrowserManager(headless=False, wizard_mode=self.wizard_mode)  # Stealth Probe
            await browser.start()
            try:
                await browser.navigate(self.session["url"], timeout=PROBE_NAVIGATION_TIMEOUT)
                scanner = Scanner(browser.page)
                return await scanner.scan(self.session["url"], wizard_mode=self.wizard_mode, timeout=PROBE_NAVIGATION_TIMEOUT)
            except Exception as e:
                log(f"Probe failed: {e}", level="warning")
                raise
            finally:
                await browser.close()

        try:
            profile = asyncio.run(do_prescan())
        except Exception as e:
            log(f"Complexity analysis probe failed completely: {e}", level="error")
            # Default to a safe fallback instead of failing
            profile = {"access_recommendation": "guided", "complexity_score": 100, "complexity_reasons": ["Probe failed"]}
        
        rec = profile.get("access_recommendation", "automatic")
        score = profile.get("complexity_score", 0)
        reasons = ", ".join(profile.get("complexity_reasons", []))
        
        if not self.wizard_mode:
            log(f"Complexity Analysis: Score={score}, Rec={rec}, Reasons={reasons}")

        # 2. Ask User (or auto-decide in wizard mode)
        if self.wizard_mode:
            # Wizard mode: auto-decide, no question
            mode = rec  # Use scanner recommendation directly
            if mode == "guided":
                self._narrate("I've detected some bot defenses or a complex login. I'll need your help in a real browser.")
                print("\n🌐 This website blocks bots, so we'll open a real browser.\n")
                print("Please use the browser like you normally would:")
                print("  • Log in if needed")
                print("  • Search or filter to what you want")
                print("  • Scroll until the items you want are visible\n")
                print("When the screen shows exactly what you want scraped,")
                print("come back here and press Enter.\n")
        else:
            # Expert mode: ask user
            mode = UI.ask_access_mode(recommendation=rec, reason=reasons)
            
        interaction_log = {"access_mode": mode, "complexity_score": score, "steps": []}
        safe_write_json(self.project_dir / "interaction.json", interaction_log)
            
        if mode == "guided":
            self._transition_to(State.GUIDED_ACCESS)
        else:
            self._transition_to(State.RECON)

    def _handle_guided_access(self):
        """Guided Access via visible browser (Replaces Login)."""
        if self.ci_mode:
            log("CI Mode: Bypassing guided access. Proceeding to RECON.", level="warning")
            self._transition_to(State.RECON)
            return

        if not self.wizard_mode:
            log("Starting Guided Access Phase...")
        
        async def do_login():
            browser = BrowserManager(headless=False, wizard_mode=self.wizard_mode)
            await browser.start()
            try:
                url = self.session["url"]
                print(f"Opening {url} ...")
                print("1. Please Navigate / Search / Filter to reach your target data.")
                print("2. Log in if required.")
                print("3. Ensure the data you want to scrape is VISIBLE on screen.")
                print("   (ScrapeWizard will capture your final page state and session)")
                await browser.navigate(url)
                
                input("Press ENTER when you are ready to scrape this exact view...")
                
                cookies = await browser.get_cookies()
                storage_state = await browser.get_storage_state()
                final_url = browser.page.url
                
                safe_write_json(self.project_dir / "cookies.json", cookies)
                safe_write_json(self.project_dir / "storage_state.json", storage_state)
                
                self.session["url"] = final_url
                self.session["login_performed"] = True
                
            finally:
                await browser.close()
        
        asyncio.run(do_login())
        
        # UI prompts AFTER async block
        UX.print_success("Session captured (will reuse cookies in generated script)")
            
        self._transition_to(State.RECON)

    def _handle_recon(self) -> None:
        """Step 2: Run browser reconnaissance."""
        self._progress_step(2, "Understanding structure", duration=3.0)
        self._narrate("I'm now performing a 'Behavioral Scan'. I observe how the page loads, clicks, and scrolls to identify the data patterns.")

        if not self.wizard_mode:
            log("Starting Reconnaissance...")
        
        cookies = safe_read_json(self.project_dir / "cookies.json")
        storage_state = safe_read_json(self.project_dir / "storage_state.json")

        @retry(
            wait=wait_exponential(multiplier=1, min=2, max=10),
            stop=stop_after_attempt(2),
            retry=retry_if_exception_type((Exception)),
            reraise=True
        )
        async def do_recon():
            # Use headed mode if login was performed, as requested by user
            use_headless = not self.session.get("login_performed", False)
            browser = BrowserManager(headless=use_headless, storage_state=storage_state, wizard_mode=self.wizard_mode)
            await browser.start()
            try:
                # If no storage_state but we have legacy cookies, inject them
                if not storage_state and cookies:
                    await browser.inject_cookies(cookies)
                    
                await browser.navigate(self.session["url"], timeout=SCAN_NAVIGATION_TIMEOUT)
                
                # 0. Health Check (Bot Detection)
                health = await browser.check_health()
                if health["blocked"]:
                    self._narrate(f"Wait! I've been detected by {', '.join(health['reasons'])}. I'll need to enter Interactive Mode to solve this.")
                    return "needs_solve"

                # 1. Run Behavioral Scan
                scanner = Scanner(browser.page)
                scan_profile = await scanner.scan(self.session["url"], wizard_mode=self.wizard_mode, timeout=SCAN_NAVIGATION_TIMEOUT)
                
                # Save Scan Profile
                safe_write_json(self.project_dir / "scan_profile.json", scan_profile)
                
                html = await browser.get_content()
                
                await browser.take_screenshot(self.project_dir / "debug_recon.png")
                
                # Analyze
                analyzer = DOMAnalyzer(html)
                analysis = analyzer.analyze()
                
                pg_detector = PaginationDetector(analyzer.soup, self.session["url"])
                analysis["pagination"] = pg_detector.detect()
                
                tech_detector = TechFingerprinter(analyzer.soup)
                analysis["meta"] = {
                    "url": self.session["url"],
                    "title": await browser.page.title(),
                    "detected_tech": tech_detector.detect()
                }
                analysis["interaction_used"] = False
                
                safe_write_json(self.project_dir / "analysis_snapshot.json", analysis)
                
                return "ok"
                    
            finally:
                await browser.close()
        
        try:
            result = asyncio.run(do_recon())
        except Exception as e:
            log(f"Reconnaissance failed completely: {e}", level="error")
            self._transition_to(State.FAILED)
            return
        
        if result == "needs_solve":
            self._transition_to(State.INTERACTIVE_SOLVE)
            return

        # Check for CAPTCHA from scanner profile as well
        profile = safe_read_json(self.project_dir / "scan_profile.json")
            
        if profile.get("tech_stack", {}).get("anti_bot", {}).get("captcha") and not self.ci_mode:
            self._transition_to(State.INTERACTIVE_SOLVE)
        else:
            self._transition_to(State.LLM_ANALYSIS)

    def _handle_interactive_solve(self):
        """HITL: Let user solve CAPTCHA/Blocker manually."""
        log("Entering INTERACTIVE_SOLVE state...")
        
        async def do_solve():
            browser = BrowserManager(headless=False)
            await browser.start()
            try:
                await browser.navigate(self.session["url"])
                # Wait for user
                if await UI.wait_for_solve(reason="CAPTCHA or blocking screen detected."):
                    # Capture current state after solve
                    log("User confirmed solve. Re-scanning page state...")
                    try:
                        scanner = Scanner(browser.page)
                        # Reduced timeout for these post-solve captures to fail fast if closed
                        scan_profile = await scanner.scan(browser.page.url, timeout=10)
                        
                        safe_write_json(self.project_dir / "scan_profile.json", scan_profile)
                            
                        # Capture full storage state after solve
                        storage_state = await browser.get_storage_state()
                        safe_write_json(self.project_dir / "storage_state.json", storage_state)
                            
                        html = await browser.get_content()
                        analyzer = DOMAnalyzer(html)
                        analysis = analyzer.analyze()
                        
                        safe_write_json(self.project_dir / "analysis_snapshot.json", analysis)
                            
                        # Capture interaction: user solved captcha
                        interaction = {"captcha_solved_manually": True, "final_url": browser.page.url}
                        safe_write_json(self.project_dir / "interaction.json", interaction)
                            
                        # Also capture cookies to bypass future CAPTCHAs
                        cookies = await browser.get_cookies()
                        safe_write_json(self.project_dir / "cookies.json", cookies)
                            
                        log("Cookies saved for generated script.")
                    except Exception as e:
                        if "TargetClosed" in str(e):
                            log("Browser closed by user during capture. Aborting.", level="error")
                        else:
                            log(f"Error capturing post-solve state: {e}", level="error")
                        return False
                else:
                    log("User cancelled solve.", level="warning")
                    self._transition_to(State.FAILED)
                    return False
                return True
            finally:
                await browser.close()
                
        if asyncio.run(do_solve()):
            self._transition_to(State.LLM_ANALYSIS)

    def _handle_llm_analysis(self) -> None:
        """Step 3: Call LLM for understanding."""
        self._progress_step(3, "Analyzing data patterns", duration=3.0)
        self._narrate("I'm using AI to understand the layout and find the best fields to scrape. I'm looking for product titles, prices, and other key details.")
        
        agent = UnderstandingAgent(self.project_dir, wizard_mode=self.wizard_mode)
        
        snapshot = safe_read_json(self.project_dir / "analysis_snapshot.json")
        interaction = safe_read_json(self.project_dir / "interaction.json")
        scan_profile = safe_read_json(self.project_dir / "scan_profile.json")
        
        understanding = agent.analyze(snapshot, scan_profile, interaction)
        
        if self.ci_mode:
            if not understanding.get("scraping_possible") or understanding.get("confidence", 0) < LLM_CONFIDENCE_THRESHOLD:
                log(f"CI Mode Aborted: {understanding.get('reason', 'Ambiguous UI detected')}", level="error")
                self._transition_to(State.FAILED)
                return
        else:
            if not understanding.get("scraping_possible", False):
                if self.wizard_mode:
                    pass  # Wizard mode: auto-continue
                elif not UI.override_llm_hallucination(understanding.get("reason", "Unknown")):
                    self._transition_to(State.FAILED)
                    return

        self._transition_to(State.USER_CONFIG)

    def _handle_user_config(self) -> None:
        """Step 4: Get user selections for fields, pagination, format."""
        self._progress_step(4, "Selecting data", duration=1.0)
        
        understanding = safe_read_json(self.project_dir / "llm_understanding.json")
            
        if self.ci_mode:
            # Smart defaults for CI
            fields = [f.get('name') for f in understanding.get("available_fields", [])][:5] # Limit to 5
            if not fields:
                fields = ["item_title", "item_price"] # Generic fallback
            pagination = "first_page"
            fmt = "json"
            browser_mode = understanding.get("recommended_browser_mode", "headless")
            log(f"CI Mode: Using defaults - Fields: {fields}, Pagination: {pagination}, Format: {fmt}, Browser Mode: {browser_mode}")
        else:
            all_fields = understanding.get("available_fields", [])
            
            # Zero-Click / Wizard Mode Logic
            if self.wizard_mode:
                # 1. Fields: Auto-suggest without prompting (unless interactive requested)
                suggested = [f for f in all_fields if f.get('suggested')]
                if not suggested:
                    suggested = all_fields[:5] # Fallback
                
                # Only ask if specifically interactive, otherwise just take suggestions
                # (Note: self.interactive_mode logic would be passed here if we had that flag separately)
                # For now, wizard_mode implies Zero-Click unless we find a way to pass 'interactive'
                # But UI.ask_fields_wizard defaults to interactive dialog. 
                # We need to change that: pass interactive=False by default for Zero-Click
                
                # Assumption: self.interactive_mode should be a new flag on Orchestrator
                interactive = getattr(self, "interactive_mode", False)
                fields = UI.ask_fields_wizard(all_fields, suggested, interactive=interactive)
                
                if fields == "retry":
                    self._narrate("Understood. I'll take a deeper look at the page structure.")
                    self._transition_to(State.RECON)
                    return

                # Gate 1: Output Format (User owns WHAT)
                fmt = UI.ask_format()

                # Gate 2: Pagination Scope (User owns WHAT)
                pagination = UI.ask_pagination()
                
                # Browser Mode: AI Recommendation (Orchestrator recommended WHEN)
                browser_mode = understanding.get("recommended_browser_mode", "headless")
                if self.session.get("login_performed", False):
                     browser_mode = "headed"
                
                # Logic to convert UI choices to Runtime config
                pagination_config = {
                    "mode": "all" if pagination == "all_pages" else "first_page",
                    "max_pages": 5 if pagination == "limit_5" else (50 if pagination == "all_pages" else 1)
                }
                
            else:
                # Expert Mode: Full selection
                fields = UI.ask_fields(all_fields)
                pagination = UI.ask_pagination()
                fmt = UI.ask_format()
                recommended_mode = understanding.get("recommended_browser_mode", "headless")
                reason = understanding.get("reason", "No reason provided")
                if self.session.get("login_performed", False):
                    recommended_mode = "headed"
                    reason = "Login performed."
                browser_mode = UI.confirm_browser_mode(recommended_mode, reason, wizard_mode=False)
                
                # Expert Mode also needs pagination_config
                pagination_config = {
                    "mode": "all" if pagination == "all_pages" else "first_page",
                    "max_pages": 5 if pagination == "limit_5" else (50 if pagination == "all_pages" else 1)
                }
        
        config = {
            "fields": fields,
            "pagination": pagination,
            "pagination_config": pagination_config,
            "format": fmt,
            "browser_mode": browser_mode
        }
        
        safe_write_json(self.project_dir / "run_config.json", config)
            
        self._transition_to(State.CODEGEN)

    def _handle_codegen(self) -> None:
        """Step 5: Generate scraper code via LLM."""
        self._progress_step(5, "Writing scraper", duration=4.0)
        self._narrate("I'm now writing the actual Python code for your scraper. I use Playwright as the engine because it's great at handling modern websites.")
        
        agent = CodeGenerator(self.project_dir, wizard_mode=self.wizard_mode)
        
        snapshot = safe_read_json(self.project_dir / "analysis_snapshot.json")
        understanding = safe_read_json(self.project_dir / "llm_understanding.json")
        run_config = safe_read_json(self.project_dir / "run_config.json")
        scan_profile = safe_read_json(self.project_dir / "scan_profile.json")
        interaction = safe_read_json(self.project_dir / "interaction.json")

        @retry(
            wait=wait_exponential(multiplier=1, min=2, max=10),
            stop=stop_after_attempt(2),
            retry=retry_if_exception_type((Exception)),
            reraise=True
        )
        def do_gen():
            agent.generate(snapshot, understanding, run_config, scan_profile, interaction)
        
        do_gen()
        self._transition_to(State.TEST)

    def _handle_test(self) -> None:
        """Step 6: Run auto-test on generated scraper with rich data preview."""
        self._progress_step(6, "Testing", duration=2.0)
        self._narrate("I'm running a quick test of the generated script to make sure it can correctly extract data from the page.")

        if not self.wizard_mode:
            log("Running auto-test on generated scraper...")
        
        success, output = ScriptTester.run_test(
            self.project_dir / "generated_scraper.py",
            self.project_dir,
            timeout=DEFAULT_SCRIPT_TIMEOUT,
            wizard_mode=self.wizard_mode
        )
        
        if success:
            if not self.wizard_mode:
                log("Test Passed!")
            
            # Load and preview the data
            data = self._load_output_data()
            
            if self.ci_mode:
                if data:
                    log(f"CI Mode: Test passed with {len(data)} rows. Auto-approving.")
                    self._transition_to(State.APPROVED)
                else:
                    log("CI Mode: Test passed but no data returned. Failing.", level="error")
                    self._transition_to(State.FAILED)
                return

            if data:
                # Zero-Click / Wizard Mode Logic
                if self.wizard_mode and not self.interactive_mode:
                    has_issues = UI.show_smart_preview(data)
                    
                    if not has_issues:
                        UX.print_success("Auto-test passed. Proceeding with full scrape.")
                        self._transition_to(State.APPROVED)
                        return
                    else:
                        # Fall through to manual review if issues found
                        log("Data quality issues detected in Wizard Mode. Switching to manual review.")

                # Interactive Mode: Detailed review
                action, bad_cols = UI.review_data_quality(data)
                
                if action == "approve":
                    self._transition_to(State.APPROVED)
                elif action == "fix_columns":
                    # Store columns to fix and trigger repair
                    self.session["fix_columns"] = bad_cols
                    log(f"User flagged columns for repair: {bad_cols}")
                    self._transition_to(State.REPAIR)
                elif action == "guided":
                    # Go back to GUIDED_ACCESS
                    self.session["force_guided"] = True
                    log("Switching to Guided Mode for manual page adjustment.")
                    self._transition_to(State.GUIDED_ACCESS)
                elif action == "retry":
                    # Go back to config, not just codegen
                    if not self.wizard_mode:
                        log("User requested re-configuration.")
                    self._transition_to(State.USER_CONFIG)
                else:  # abort
                    if not self.wizard_mode:
                        log("User aborted.")
                    self._transition_to(State.DONE)
            else:
                # No data...
                if self.wizard_mode and not self.interactive_mode:
                     UX.print_warning("Test run completed but no data returned. Check logs.")
                     self._transition_to(State.DONE)
                else: 
                    # No data but script ran - simple approval
                    if UI.approve_run():
                        self._transition_to(State.APPROVED)
                    else:
                        self._transition_to(State.DONE)
        else:
            if self.ci_mode or (self.wizard_mode and not self.interactive_mode):
                # Auto-repair in Zero-Click mode? 
                # For now, let's just fail or try one repair. 
                # The prompt implies "Zero-Click" should just work or report.
                log(f"Test Failed. Output: {output[:200]}...", level="error")
                # Trigger repair automatically in Zero-Click?
                # Let's try repair.
                self._transition_to(State.REPAIR)
                return


            action = UI.ask_test_failure_action(output)
            if action == "repair":
                self._transition_to(State.REPAIR)
            elif action == "config":
                self._transition_to(State.USER_CONFIG)
            elif action == "edit":
                # Manual Edit - future feature, for now just log
                log(f"Manual edit requested. Script is at: {self.project_dir}/generated_scraper.py")
                input("Press ENTER when you have finished editing the script...")
                self._transition_to(State.TEST)
            else:
                self._transition_to(State.FAILED)

    def _load_output_data(self):
        """Load output/data.json if exists."""
        return safe_read_json(self.project_dir / "output" / "data.json", default=None)

    def _handle_repair(self) -> None:
        """Self-healing repair loop with optional column-specific hints."""
        self._progress_step(5, "Self-healing", duration=2.0)
        self._narrate("The test failed, so I'm investigating the error. I'll automatically try to find more stable selectors and fix the script.")
        
        loop = RepairLoop(self.project_dir, wizard_mode=self.wizard_mode)
        
        # Check if user flagged specific columns
        fix_columns = self.session.get("fix_columns", None)
        if fix_columns:
            log(f"Attempting to fix columns: {fix_columns}")
            # We'll pass this hint to repair agent
            self.session.pop("fix_columns", None)
        
        def runner():
            return ScriptTester.run_test(
                self.project_dir / "generated_scraper.py",
                self.project_dir,
                timeout=DEFAULT_SCRIPT_TIMEOUT,
                wizard_mode=self.wizard_mode
            )
        
        # Run repair with column hints if available
        fixed = loop.run(
            self.project_dir / "generated_scraper.py", 
            runner,
            column_hints=fix_columns
        )
        
        if fixed:
            if self.ci_mode:
                log("CI Mode: Repair successful. Auto-approving.")
                self._transition_to(State.APPROVED)
                return

            # Show data again after fix
            data = self._load_output_data()
            if data:
                action, bad_cols = UI.review_data_quality(data)
                if action == "approve":
                    self._transition_to(State.APPROVED)
                elif action == "fix_columns":
                    self.session["fix_columns"] = bad_cols
                    if not self.wizard_mode:
                        log("User requested another fix round.")
                    # Stay in REPAIR but we've exhausted attempts
                    self._transition_to(State.FAILED)
                elif action == "retry":
                    if not self.wizard_mode:
                        log("User requested regeneration.")
                    self._transition_to(State.CODEGEN)
                else:
                    if not self.wizard_mode:
                        log("User aborted.")
                    self._transition_to(State.DONE)
            else:
                if UI.approve_run():
                    self._transition_to(State.APPROVED)
                else:
                    self._transition_to(State.DONE)
        else:
            if self.ci_mode:
                if not self.wizard_mode:
                    log("Repair failed. Proceeding to FAILED state.", level="error")
                self._transition_to(State.FAILED)
                return

            action = UI.ask_repair_failure_action()
            if action == "config":
                self._transition_to(State.USER_CONFIG)
            elif action == "edit":
                log(f"Manual edit requested. Script is at: {self.project_dir}/generated_scraper.py")
                input("Press ENTER when you have finished editing the script...")
                self._transition_to(State.TEST)
            else:
                self._transition_to(State.FAILED)

    def _handle_final_run(self) -> None:
        """Final scraping run and bundle output."""
        self._progress_step(6, "Final Scrape", duration=3.0)
        self._narrate("Testing complete! I'm now running the full scraper to collect all the data and bundle everything up for you.")

        if not self.wizard_mode:
            log("Starting Final Run...")
        
        # Final run gets a much longer timeout (10 minutes)
        @retry(
            wait=wait_exponential(multiplier=1, min=2, max=30),
            stop=stop_after_attempt(2),
            retry=retry_if_exception_type((Exception)),
            reraise=True
        )
        def do_final():
            return ScriptTester.run_test(
                self.project_dir / "generated_scraper.py",
                self.project_dir,
                timeout=600,
                wizard_mode=self.wizard_mode
            )
            
        success, output = do_final()
        
        if success:
            # Bundle all project files into output folder
            self._bundle_output()
            
            if self.wizard_mode:
                output_format = self.session.get('format', 'xlsx')
                output_file = self.project_dir / "output" / f"data.{output_format}"
                print(f"\n✅ Done!\n")
                print(f"Your data is ready:")
                print(f"{output_file}\n")
            else:
                log(f"Final run complete. All files bundled in {self.project_dir}/output")
            self._transition_to(State.DONE)
        else:
            if not self.wizard_mode:
                log("Final run failed.")
            self._transition_to(State.FAILED)

    def _bundle_output(self) -> None:
        """
        Copy all relevant project files into the output folder for portability.
        User requested: script, logs, JSON configs, .env all in one place.
        """
        import shutil
        output_dir = self.project_dir / "output"
        output_dir.mkdir(exist_ok=True)
        
        # Files to copy
        files_to_bundle = [
            "generated_scraper.py",
            "analysis_snapshot.json",
            "llm_understanding.json",
            "run_config.json",
            "session.json",
            "interaction.json",
            "cookies.json",
            ".env"
        ]
        
        for fname in files_to_bundle:
            src = self.project_dir / fname
            if src.exists():
                shutil.copy2(src, output_dir / fname)
        
        # Copy logs folder
        logs_src = self.project_dir / "logs"
        logs_dst = output_dir / "logs"
        if logs_src.exists():
            if logs_dst.exists():
                shutil.rmtree(logs_dst)
            shutil.copytree(logs_src, logs_dst)
        
        # Copy llm_logs folder
        llm_logs_src = self.project_dir / "llm_logs"
        llm_logs_dst = output_dir / "llm_logs"
        if llm_logs_src.exists():
            if llm_logs_dst.exists():
                shutil.rmtree(llm_logs_dst)
            shutil.copytree(llm_logs_src, llm_logs_dst)
        
        if not self.wizard_mode:
            log("Project files bundled into output folder.")
