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

    def analyze(self) -> Dict[str, Any]:
        """Perform full analysis."""
        return {
            "sections": self._detect_repeating_sections(),
            # "pagination": ... (calculated separately or here)
        }

    def _detect_repeating_sections(self) -> List[Dict]:
        """
        Identify repeating blocks (e.g., product cards) by analyzing class distribution.
        """
        # Collect all tags with classes
        tag_classes = []
        for tag in self.soup.find_all(True):
            if tag.get("class"):
                # Tuple of sorted classes makes it hashable
                classes = tuple(sorted(tag.get("class")))
                tag_classes.append((tag.name, classes))
        
        # Count occurrences
        counts = Counter(tag_classes)
        
        # Filter for significant repetition (e.g. > 3 times)
        sections = []
        for (tag_name, classes), count in counts.most_common(10):
            if count > 2:
                # Generate a selector for this group
                class_selector = "." + ".".join(classes)
                full_selector = f"{tag_name}{class_selector}"
                
                # Check what fields are inside one instance
                example_el = self.soup.select_one(full_selector)
                if not example_el: continue
                fields = self._extract_potential_fields(example_el)
                
                if fields:
                    sections.append({
                        "type": "repeating_list",
                        "selector": full_selector,
                        "count": count,
                        "fields": fields
                    })
                    
        return sections

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
                if parent.get("class"):
                    css += "." + ".".join(parent.get("class"))
                
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
