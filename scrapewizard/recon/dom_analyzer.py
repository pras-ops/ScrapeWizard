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
        if len(children) >= 2:
            return True
            
        # Recursive check: if it has a single child that is rich
        if len(children) == 1:
            return self._is_rich_container(children[0])
            
        return False

    def _detect_repeating_sections(self) -> List[Dict]:
        """
        Identify repeating blocks (e.g., product cards) by analyzing class distribution.
        Prioritizes deeper/richer nodes to avoid utility links in footers/sidebars.
        """
        # Collect all tags with filtered "safe" classes
        tag_groups = []
        for tag in self.soup.find_all(True):
            if tag.name in ["script", "style", "noscript", "svg", "link", "meta", "nav", "footer", "header"]:
                continue
            
            raw_classes = tag.get("class", [])
            # Filter classes BEFORE grouping so that elements with (SharedClass + UniqueID) group together
            safe_classes = tuple(sorted([c for c in raw_classes if self._is_safe_class(c)]))
            
            if safe_classes:
                tag_groups.append((tag.name, safe_classes))
        
        # Count occurrences of (Tag + SafeClasses)
        counts = Counter(tag_groups)
        
        sections = []
        # Look at more candidates to find the richest one
        for (tag_name, classes), count in counts.most_common(30):
            if count > 2:
                class_selector = "." + ".".join(classes)
                full_selector = f"{tag_name}{class_selector}"
                
                # Check what fields are inside one instance
                example_el = self.soup.select_one(full_selector)
                if not example_el:
                    continue
                
                # Minimum richness check (loosened)
                if not self._is_rich_container(example_el):
                    # Even if not "rich", if it has a high count and some text, it might be a simple list
                    text_content = example_el.get_text(strip=True)
                    if len(text_content) < 5:
                        continue
                
                fields = self._extract_potential_fields(example_el)
                
                if fields:
                    # Heuristic: richer nodes (more fields) are better candidates
                    # Multiply by log(count) or similar to balance field density vs frequency
                    score = len(fields) * (count ** 0.5)
                    sections.append({
                        "type": "repeating_list",
                        "selector": full_selector,
                        "count": count,
                        "fields": fields,
                        "score": score
                    })

        # Sort by score descending and return
        sections.sort(key=lambda x: x["score"], reverse=True)
        return sections[:12]

    def _extract_potential_fields(self, element) -> List[Dict]:
        """
        Look for text/links/images inside a container element.
        """
        fields = []
        seen_selectors = set()
        
        # Text fields (titles, prices, ratings)
        for child in element.find_all(text=True, recursive=True):
            text = child.strip()
            # Allow slightly longer text for descriptions
            if 1 < len(text) < 250:
                parent = child.parent
                tag = parent.name
                
                if tag in ["script", "style", "noscript"]:
                    continue
                
                # Try to get a valid selector
                raw_classes = parent.get("class", [])
                safe_classes = [c for c in raw_classes if self._is_safe_class(c)]
                
                if safe_classes:
                    css = f"{tag}." + ".".join(safe_classes)
                else:
                    css = tag
                
                if css not in seen_selectors:
                    fields.append({
                        "name": "text_field",
                        "css": css,
                        "sample": text[:50]
                    })
                    seen_selectors.add(css)

        # Links (Prioritize those with high-level classes)
        for link in element.find_all("a", href=True):
            raw_classes = link.get("class", [])
            safe_classes = [c for c in raw_classes if self._is_safe_class(c)]
            css = "a" + ("." + ".".join(safe_classes) if safe_classes else "")
            
            if css not in seen_selectors:
                fields.append({
                    "name": "link",
                    "css": css,
                    "sample": link['href'][:50]
                })
                seen_selectors.add(css)

        # Images
        for img in element.find_all("img", src=True):
            raw_classes = img.get("class", [])
            safe_classes = [c for c in raw_classes if self._is_safe_class(c)]
            css = "img" + ("." + ".".join(safe_classes) if safe_classes else "")
            
            if css not in seen_selectors:
                fields.append({
                    "name": "image",
                    "css": css,
                    "sample": img['src'][:50]
                })
                seen_selectors.add(css)
            
        return fields
