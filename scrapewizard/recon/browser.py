import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from scrapewizard.core.logging import log
from scrapewizard.core.constants import (
    DEFAULT_BROWSER_TIMEOUT,
    DEFAULT_USER_AGENT
)

class BrowserManager:
    """
    Manages Playwright browser session for reconnaissance and recording.
    """
    def __init__(self, headless: bool = True, proxy: Optional[Dict] = None, storage_state: Optional[Dict] = None, wizard_mode: bool = False):
        self.headless = headless
        self.proxy = proxy
        self.storage_state = storage_state
        self.wizard_mode = wizard_mode
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.recorded_events = []

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self) -> None:
        """Start the browser session."""
        self.playwright = await async_playwright().start()
        
        launch_args = {
            "headless": self.headless,
        }
        
        # Add stealth arguments for headed mode to bypass automation detection
        if not self.headless:
            launch_args["args"] = ["--disable-blink-features=AutomationControlled"]
        
        if self.proxy:
             launch_args["proxy"] = self.proxy

        self.browser = await self.playwright.chromium.launch(**launch_args)
        
        # Standard user agent from constants to avoid basic blocking
        context_args = {
             "user_agent": DEFAULT_USER_AGENT,
             "viewport": {"width": 1280, "height": 800}
        }
        if self.storage_state:
            context_args["storage_state"] = self.storage_state

        self.context = await self.browser.new_context(**context_args)
        self.page = await self.context.new_page()

    async def close(self) -> None:
        """Close the browser session."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def navigate(self, url: str, timeout: Optional[int] = None) -> Optional[Any]:
        """Navigate to a URL with error handling."""
        if not self.wizard_mode:
            log(f"Navigating to {url}")
        
        # Use provided timeout or global default (multiplied by 1000 for ms)
        timeout_ms = (timeout or DEFAULT_BROWSER_TIMEOUT) * 1000
        
        try:
            response = await self.page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await self.page.wait_for_timeout(2000) # Grace period
            return response
        except Exception as e:
            if not self.wizard_mode:
                log(f"Navigation failed: {e}", level="error")
            raise

    async def check_health(self) -> Dict[str, Any]:
        """Check if the page is healthy or blocked by bots."""
        content = await self.page.content()
        content_lower = content.lower()
        
        blocks = []
        if any(p in content_lower for p in ["cloudflare", "ray id", "checking your browser"]):
            blocks.append("Cloudflare Challenge")
        if any(p in content_lower for p in ["akamai", "access denied", "reference #"]):
            blocks.append("Akamai/WAF Block")
        if "px-captcha" in content_lower or "perimeterx" in content_lower:
            blocks.append("PerimeterX CAPTCHA")
        if "bot detection" in content_lower or "automated access" in content_lower:
            blocks.append("Generic Bot Detection")
        if "amazon" in content_lower and "robot" in content_lower:
            blocks.append("Amazon Robot Check")
            
        return {
            "blocked": len(blocks) > 0,
            "reasons": blocks,
            "title": await self.page.title()
        }

    async def get_content(self) -> str:
        """Get current page HTML."""
        return await self.page.content()

    async def take_screenshot(self, path: Path) -> None:
        """Save a screenshot."""
        await self.page.screenshot(path=str(path))

    async def get_cookies(self) -> List[Dict]:
        """Get current cookies."""
        return await self.context.cookies()

    async def get_storage_state(self) -> Dict[str, Any]:
        """Get full storage state (cookies + local storage)."""
        return await self.context.storage_state()

    async def inject_cookies(self, cookies: List[Dict]) -> None:
        """Inject cookies into context."""
        await self.context.add_cookies(cookies)

    async def start_interactive_recording(self) -> List[Dict]:
        """Inject scripts to record user interactions."""
        # Define the bridge function to receive events from JS
        async def on_event(event_type: str, selector: str, value: str) -> None:
            if not self.wizard_mode:
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
