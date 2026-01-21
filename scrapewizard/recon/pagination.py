from bs4 import BeautifulSoup
from typing import Dict, Any

class PaginationDetector:
    """
    Detects pagination mechanisms on a page.
    """
    
    def __init__(self, soup: BeautifulSoup, url: str):
        self.soup = soup
        self.url = url

    def detect(self) -> Dict[str, Any]:
        """Run detection heuristics."""
        
        # 1. Look for 'Next' button
        next_button = self._find_next_button()
        if next_button:
            return {
                "detected": True,
                "type": "next_button",
                "selector": next_button
            }
            
        # 2. Look for URL patterns (simple check)
        if "page=" in self.url or "/p/" in self.url:
             return {
                "detected": True,
                "type": "url_param",
                "param": "guessed_from_url"
            }

        return {"detected": False, "type": "none"}

    def _find_next_button(self) -> str:
        """Heuristic for next button."""
        # Check text content
        candidates = self.soup.find_all(lambda tag: tag.name == 'a' or tag.name == 'button')
        
        for tag in candidates:
            text = tag.get_text().lower().strip()
            if text in ["next", "next page", ">", "»"] or "next" in str(tag.get("class", [])):
                # Construct selector
                if tag.get("id"):
                    return f"#{tag['id']}"
                if tag.get("class"):
                    return f".{'.'.join(tag['class'])}"
                if text == "next":
                    return f"{tag.name}:contains('Next')" # Pseudo-selector, careful
                
        return None
