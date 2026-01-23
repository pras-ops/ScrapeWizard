import asyncio
from playwright.async_api import async_playwright, Page, BrowserContext
from typing import Optional, Dict

class Runtime:
    def __init__(self, headless: bool = True, storage_state: Optional[str] = None, output_format: str = "json", pagination_config: Dict = None):
        self.headless = headless
        self.storage_state = storage_state
        self.output_format = output_format
        self.pagination_config = pagination_config or {"mode": "first_page", "max_pages": 1}
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(storage_state=self.storage_state)
        self.page = await self.context.new_page()

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def smart_wait(self, selector: str, timeout: int = 15000, state: str = "visible"):
        """Dynamic waiting function: waits for element to be loaded and ready."""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout, state=state)
        except Exception:
            print(f"Warning: Timeout waiting for selector {selector} ({state})")

    async def wait_for_idle(self, timeout: int = 5000):
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass

    async def scroll_down(self, times: int = 1, delay: float = 1.0):
        """Scroll down the page to trigger lazy loading."""
        for _ in range(times):
            await self.page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(delay)
