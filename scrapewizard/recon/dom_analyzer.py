from bs4 import BeautifulSoup
from collections import Counter
import re
from typing import Dict, List, Any

class DOMAnalyzer:
    """
    Analyzes HTML to detect structure, repeating elements, and potential data fields.
    """
    
    def __init__(self, html: str):
        self.soup = BeautifulSoup(html, "lxml")
        self.html_len = len(html)
        self.SAFE_CLASS_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

    def analyze(self) -> Dict[str, Any]:
        """Perform full analysis."""
        return {
            "sections": self._detect_repeating_sections(),
        }

    def _is_safe_class(self, cls: str) -> bool:
        """
        Only allow classes that are safe for CSS selectors
        across BeautifulSoup, SoupSieve, and Playwright.
        """
        if not cls:
            return False
        return self.SAFE_CLASS_RE.match(cls) is not None

    def _is_rich_container(self, el) -> bool:
        """
        Check if a container element has enough structure to be a content block.
        Prevents picking shallow UI elements like single links or buttons.
        """
        children = [c for c in el.find_all(recursive=False) if c.name]
        return (
            len(children) >= 2 and
            len(set(child.name for child in children)) >= 2
        )

    def _detect_repeating_sections(self) -> List[Dict]:
        """
        Identify repeating blocks (e.g., product cards) by analyzing class distribution.
        Prioritizes deeper/richer nodes to avoid utility links in footers/sidebars.
        """
        # Collect all tags with classes
        tag_classes = []
        for tag in self.soup.find_all(True):
            # Skip hidden or utility tags
            if tag.name in ["script", "style", "noscript", "svg", "link", "meta", "nav", "footer", "header"]:
                continue
            
            if tag.get("class"):
                # Tuple of sorted classes makes it hashable
                classes = tuple(sorted(tag.get("class")))
                tag_classes.append((tag.name, classes))
        
        # Count occurrences
        counts = Counter(tag_classes)
        
        # Filter for significant repetition (e.g. > 3 times)
        sections = []
        # Look at more candidates to find the richest one
        for (tag_name, classes), count in counts.most_common(20):
            if count > 2:
                # Filter classes to only keep safe ones
                safe_classes = [c for c in classes if self._is_safe_class(c)]
                
                # Generate a selector for this group
                if safe_classes:
                    class_selector = "." + ".".join(safe_classes)
                    full_selector = f"{tag_name}{class_selector}"
                else:
                    full_selector = tag_name
                
                # Check what fields are inside one instance
                example_el = self.soup.select_one(full_selector)
                if not example_el: continue
                
                # Minimum richness check
                if not self._is_rich_container(example_el):
                    continue
                fields = self._extract_potential_fields(example_el)
                
                if fields:
                    # Heuristic: richer nodes (more fields) are better candidates for main content
                    score = len(fields) * count
                    sections.append({
                        "type": "repeating_list",
                        "selector": full_selector,
                        "count": count,
                        "fields": fields,
                        "score": score
                    })

        # Sort by score descending and return
        sections.sort(key=lambda x: x["score"], reverse=True)
        return sections[:10]

    def _extract_potential_fields(self, element) -> List[Dict]:
        """
        Look for text/links/images inside a container element.
        """
        fields = []
        
        # Text fields (titles, prices)
        for child in element.find_all(text=True, recursive=True):
            text = child.strip()
            if len(text) > 1 and len(text) < 100:
                parent = child.parent
                tag = parent.name
                
                # Try to get a class for valid selector
                css = tag
                raw_classes = parent.get("class", [])
                safe_classes = [c for c in raw_classes if self._is_safe_class(c)]
                if safe_classes:
                    css += "." + ".".join(safe_classes)
                
                fields.append({
                    "name": "text_field", # Generic name, specific naming left to LLM
                    "css": css,
                    "sample": text[:30]
                })

        # Links
        links = element.find_all("a", href=True)
        if links:
            fields.append({
                "name": "link",
                "css": "a",
                "sample": links[0]['href']
            })

        # Images
        imgs = element.find_all("img", src=True)
        if imgs:
            fields.append({
                "name": "image",
                "css": "img",
                "sample": imgs[0]['src']
            })
            
        return fields
