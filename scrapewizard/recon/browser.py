import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from scrapewizard.core.logging import log

class BrowserManager:
    """
    Manages Playwright browser session for reconnaissance and recording.
    """
    def __init__(self, headless: bool = True, proxy: Optional[Dict] = None):
        self.headless = headless
        self.proxy = proxy
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.recorded_events = []

    async def start(self):
        """Start the browser session."""
        self.playwright = await async_playwright().start()
        
        launch_args = {
            "headless": self.headless,
        }
        if self.proxy:
             launch_args["proxy"] = self.proxy

        self.browser = await self.playwright.chromium.launch(**launch_args)
        
        # Standard user agent to avoid basic blocking
        self.context = await self.browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
             viewport={"width": 1280, "height": 800}
        )
        self.page = await self.context.new_page()

    async def close(self):
        """Close the browser session."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def navigate(self, url: str):
        """Navigate to a URL with error handling."""
        log(f"Navigating to {url}")
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(2000) # Grace period
        except Exception as e:
            log(f"Navigation failed: {e}", level="error")
            raise

    async def get_content(self) -> str:
        """Get current page HTML."""
        return await self.page.content()

    async def take_screenshot(self, path: Path):
        """Save a screenshot."""
        await self.page.screenshot(path=str(path))

    async def get_cookies(self) -> List[Dict]:
        """Get current cookies."""
        return await self.context.cookies()

    async def inject_cookies(self, cookies: List[Dict]):
        """Inject cookies into context."""
        await self.context.add_cookies(cookies)

    async def start_interactive_recording(self) -> List[Dict]:
        """
        Inject scripts to record user interactions.
        Returns a list of recorded events when the user is done (signaled via input or close).
        NOTE: For MVP, we might just return final state, but recording clicks is planned.
        """
        # Define the bridge function to receive events from JS
        async def on_event(event_type, selector, value):
            log(f"Recorded: {event_type} on {selector}")
            self.recorded_events.append({
                "type": event_type,
                "selector": selector,
                "value": value,
                "timestamp": asyncio.get_event_loop().time()
            })

        await self.page.expose_function("recordPy", on_event)
        
        # Inject event listeners
        init_script = """
        document.addEventListener('click', (e) => {
            const target = e.target;
            // Simple selector generation logic (can be improved)
            let selector = target.tagName.toLowerCase();
            if (target.id) selector += '#' + target.id;
            else if (target.className) selector += '.' + target.className.split(' ').join('.');
            
            window.recordPy('click', selector, '');
        }, true);
        
        document.addEventListener('change', (e) => {
             const target = e.target;
             let selector = target.tagName.toLowerCase();
             if (target.id) selector += '#' + target.id;
             window.recordPy('input', selector, target.value);
        }, true);
        """
        await self.page.add_init_script(init_script)
        
        return self.recorded_events
