import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from playwright.async_api import async_playwright
from scrapewizard.engine.fingerprint import capture_from_page
from scrapewizard.core.logging import log

class InteractiveRecorder:
    """
    Headed browser recorder that captures user interaction flows with full element fingerprints.
    Generates a structured flow.json containing action steps, assertions, and metadata.
    """
    def __init__(self, output_path: str = "flow.json", screenshots_dir: str = "screenshots", headless: bool = False):
        self.output_path = Path(output_path)
        self.screenshots_dir = Path(screenshots_dir)
        self.headless = headless
        self.steps = []
        self.last_url = None
        self.is_recording = False
        self.page = None

    async def start(self, start_url: str):
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.steps = []
        self.last_url = start_url
        self.is_recording = True
        
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            self.page = await context.new_page()
            
            # Expose event callback to Python
            async def on_event_callback(action: str, temp_id: str, value: str, warnings_json: str):
                if not self.is_recording:
                    return
                
                warnings = json.loads(warnings_json)
                for w in warnings:
                    log(f"Warning: {w}", level="warning")
                    print(f"⚠️  {w}")

                el = await self.page.query_selector(f"[data-sw-temp-id='{temp_id}']")
                if not el:
                    log("Could not resolve element for fingerprinting", level="warning")
                    return
                
                step_idx = len(self.steps)
                screenshot_name = f"crop_{step_idx}.png"
                screenshot_path = self.screenshots_dir / screenshot_name
                
                try:
                    # Capture fingerprint & crop screenshot of the element
                    fingerprint = await capture_from_page(self.page, el, screenshot_path=str(screenshot_path))
                    # Remove temp id attribute
                    await el.evaluate("el => el.removeAttribute('data-sw-temp-id')")
                except Exception as e:
                    log(f"Failed to capture element fingerprint: {e}", level="error")
                    return
                
                # Mask password field values for security
                recorded_value = value
                if fingerprint.attributes.get("type") == "password":
                    recorded_value = "***MASKED***"
                
                # Primary selector
                primary_selector = fingerprint.selectors[0]["value"] if fingerprint.selectors else ""
                
                step = {
                    "action": action,
                    "value": recorded_value,
                    "fingerprint": fingerprint.to_dict(),
                    "assertions": [
                        {"kind": "visible", "value": primary_selector}
                    ]
                }
                
                # Check for URL change assertion
                await asyncio.sleep(0.3)  # Give time for potential URL changes
                current_url = self.page.url
                if current_url != self.last_url:
                    step["assertions"].append({"kind": "url", "value": current_url})
                    self.last_url = current_url
                
                self.steps.append(step)
                print(f"Recorded step {step_idx + 1}: {action} on {primary_selector}")
                
            await context.expose_function("recordPy", on_event_callback)
            
            # Recording JavaScript: listens on click & change/input
            init_script = """
            (function() {
                const recordEvent = (action, target, value) => {
                    const tempId = 'sw-' + Math.random().toString(36).substring(2, 9);
                    target.setAttribute('data-sw-temp-id', tempId);
                    
                    const warnings = [];
                    if (target.tagName.toLowerCase() === 'canvas') {
                        warnings.push("Canvas element interaction recorded; automatic healing may be unstable.");
                    }
                    if (target.getRootNode() instanceof ShadowRoot) {
                        warnings.push("Element inside Shadow DOM recorded; automatic healing may be unstable.");
                    }
                    if (window.self !== window.top) {
                        warnings.push("Element inside iframe recorded; automatic healing may be unstable.");
                    }
                    
                    let val = value;
                    if (target.type === 'password') {
                        val = '***MASKED***';
                    }
                    
                    window.recordPy(action, tempId, val, JSON.stringify(warnings));
                };

                // Click listener
                document.addEventListener('click', (e) => {
                    // Do not record clicks on studio highlights overlay
                    if (e.target.id === 'sw-overlay-root' || e.target.closest('#sw-overlay-root')) return;
                    recordEvent('click', e.target, '');
                }, true);

                // Change listener
                document.addEventListener('change', (e) => {
                    const target = e.target;
                    if (target.tagName.toLowerCase() === 'input' || target.tagName.toLowerCase() === 'textarea' || target.tagName.toLowerCase() === 'select') {
                        recordEvent('fill', target, target.value);
                    }
                }, true);
            })();
            """
            
            await context.add_init_script(init_script)
            await self.page.goto(start_url)
            
            print(f"Recording started on {start_url}. Perform actions in the browser window.")
            print("Close the browser window to stop and save the recording.")
            
            # Wait for browser window to be closed
            while not self.page.is_closed():
                await asyncio.sleep(0.5)
                
            self.is_recording = False
            
        # Save steps to file
        flow_data = {
            "url": start_url,
            "steps": self.steps
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(flow_data, f, indent=2)
            
        print(f"Recording saved to {self.output_path} ({len(self.steps)} steps).")
