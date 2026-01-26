import asyncio
from typing import List, Dict, Any, Optional
from playwright.async_api import Page, Error as PlaywrightError

class NavigationExecutor:
    """
    Executes a sequence of navigation steps on a Playwright page.
    Used to replay user-recorded flows like searching or menu navigation.
    """
    def __init__(self, page: Page):
        self.page = page

    async def execute_steps(self, steps: List[Dict[str, Any]]):
        """Execute a list of steps sequentially."""
        for step in steps:
            action = step.get("type", step.get("action"))
            selector = step.get("selector")
            value = step.get("value")
            
            try:
                if action == "click":
                    print(f"  [Nav] Clicking {selector}...")
                    await self.page.click(selector, timeout=30000)
                elif action == "fill" or action == "input":
                    print(f"  [Nav] Filling {selector} with '{value}'...")
                    await self.page.fill(selector, value, timeout=30000)
                elif action == "wait":
                    wait_for = step.get("wait_for", "timeout")
                    if wait_for == "selector":
                        print(f"  [Nav] Waiting for selector {selector}...")
                        await self.page.wait_for_selector(selector, timeout=30000)
                    else:
                        delay = step.get("delay", 2000)
                        print(f"  [Nav] Waiting for {delay}ms...")
                        await self.page.wait_for_timeout(delay)
                elif action == "scroll":
                    direction = step.get("direction", "down")
                    print(f"  [Nav] Scrolling {direction}...")
                    if direction == "down":
                        await self.page.evaluate("window.scrollBy(0, window.innerHeight)")
                    else:
                        await self.page.evaluate("window.scrollBy(0, -window.innerHeight)")
                elif action == "press":
                    key = step.get("key", "Enter")
                    print(f"  [Nav] Pressing {key}...")
                    await self.page.press(selector or "body", key)
                
                # Standard wait after each action for stability
                await self.page.wait_for_timeout(1000)
                
            except Exception as e:
                print(f"  [Warning] Navigation step failed: {action} on {selector}. Error: {e}")
                # Continue with other steps if possible
