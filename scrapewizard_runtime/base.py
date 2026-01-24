import asyncio
import os
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from .runtime import Runtime
from .io import write_json, write_csv, write_excel
from .state import load_storage_state

class BaseScraper(ABC):
    def __init__(self, url: str = None, mode: str = "headless", output_format: str = "json", pagination_config: Dict = None, pagination_meta: Dict = None):
        self.url = url
        self.mode = mode
        self.output_format = output_format
        self.pagination_config = pagination_config or {"mode": "first_page", "max_pages": 1}
        self.pagination_meta = pagination_meta or {}
        self.runtime = None
        self.page = None
        self.results = []
        self.script_dir = Path(os.path.dirname(os.path.abspath(__name__ if __name__ != "__main__" else __file__)))

    @abstractmethod
    async def navigate(self):
        """Navigate to the target URL."""
        pass

    @abstractmethod
    async def get_items(self) -> List[Any]:
        """Find all item containers on the page."""
        pass

    @abstractmethod
    async def parse_item(self, item: Any) -> Dict[str, Any]:
        """Extract data from a single item container."""
        pass

    async def setup(self):
        storage_state = load_storage_state(self.script_dir)
        self.runtime = Runtime(
            headless=(self.mode == "headless"), 
            storage_state=storage_state,
            output_format=self.output_format,
            pagination_config=self.pagination_config
        )
        await self.runtime.start()
        self.page = self.runtime.page

    async def teardown(self):
        if self.runtime:
            await self.runtime.stop()

    async def collect(self):
        items = await self.get_items()
        print(f"Found {len(items)} items on page.")
        
        page_results = []
        for i, item in enumerate(items):
            try:
                data = await self.parse_item(item)
                
                # Runtime Type Check
                if data is not None and not isinstance(data, dict):
                    print(f"  [Error] Item {i}: Scraper returned {type(data).__name__} instead of a dictionary. This usually means an 'await' was missed.")
                    continue

                if data and any(val is not None for val in data.values()):
                    page_results.append(data)
                else:
                    if i < 5: # Only log first 5 to avoid spam
                        print(f"  [Debug] Item {i} returned no valid data fields.")
            except Exception as e:
                # Catch subscripting errors on coroutines specifically for better UX
                err_msg = str(e)
                if "coroutine" in err_msg and "subscriptable" in err_msg:
                    print(f"  [Critical] Item {i} failed: {err_msg}. The AI generated code that missed an 'await' before a subscript access.")
                else:
                    print(f"  [Error] Parsing item {i}: {e}")
        
        print(f"Extracted {len(page_results)} valid records from this page.")
        self.results.extend(page_results)
        
        # Robust Deduplication (across all pages)
        unique_results = []
        seen_hashes = set()
        
        for res in self.results:
            # Create a stable hash of the content
            content_str = "|".join(str(v).strip().lower() for v in res.values())
            content_hash = hash(content_str)
            
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_results.append(res)
        
        removed_count = len(self.results) - len(unique_results)
        if removed_count > 0:
            print(f"Deduplication: Removed {removed_count} duplicate records.")
            
        self.results = unique_results

    async def save(self):
        output_dir = self.script_dir / "output"
        
        # Primary JSON for internal testing
        write_json(self.results, output_dir / "data.json")
        
        # User requested format
        if self.output_format == "csv":
            write_csv(self.results, output_dir / "data.csv")
        elif self.output_format == "xlsx":
            write_excel(self.results, output_dir / "data.xlsx")
        elif self.output_format == "all":
            write_csv(self.results, output_dir / "data.csv")
            write_excel(self.results, output_dir / "data.xlsx")
            
        print(f"Saved {len(self.results)} records to {output_dir}")

    async def _handle_pagination(self) -> bool:
        """Attempts to navigate to the next page. Returns True if successful."""
        mode = self.pagination_config.get("mode", "first_page")
        if mode == "first_page":
            return False
        
        max_pages = self.pagination_config.get("max_pages", 1)
        # In-memory page counter
        if not hasattr(self, "_page_count"):
            self._page_count = 1
        
        if self._page_count >= max_pages:
            print(f"Reached max pages: {max_pages}")
            return False

        # Try to find next button from meta
        next_selector = self.pagination_meta.get("next_button_selector")
        if not next_selector:
            print("No next button selector detected.")
            return False

        try:
            # Check if button exists and is visible
            next_btn = await self.page.query_selector(next_selector)
            if next_btn and await next_btn.is_visible():
                print(f"Navigating to page {self._page_count + 1}...")
                await next_btn.click()
                await self.runtime.wait_for_idle()
                self._page_count += 1
                return True
        except Exception as e:
            print(f"Pagination error: {e}")
        
        return False

    def run(self):
        async def _run():
            await self.setup()
            try:
                await self.navigate()
                await self.runtime.wait_for_idle()
                
                # Main Extraction Loop
                while True:
                    await self.collect()
                    
                    if not await self._handle_pagination():
                        break
                
                await self.save()
            finally:
                await self.teardown()

        asyncio.run(_run())

    def preview_run(self):
        """Quick run for verification: extraction only, 1 item."""
        async def _run():
            await self.setup()
            try:
                await self.navigate()
                await self.runtime.wait_for_idle()
                
                items = await self.get_items()
                if items:
                    data = await self.parse_item(items[0])
                    if data:
                        self.results = [data]
                
                await self.save()
            finally:
                await self.teardown()

        asyncio.run(_run())
