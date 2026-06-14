import hashlib
import re
from typing import Dict, List, Any, Optional
from pathlib import Path
from scrapewizard.core.logging import log

def normalize_text(text: Optional[str]) -> str:
    """Normalize whitespace and lowercase the text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()

def compute_dom_neighborhood_hash(html_snippet: str) -> str:
    """
    Compute a stable hash of the surrounding DOM snippet.
    Strips out digits, dynamic classes/ids, and extra whitespace to make the hash robust.
    """
    if not html_snippet:
        return ""
    # Strip whitespace
    normalized = re.sub(r"\s+", "", html_snippet)
    # Strip numeric digits (often parts of dynamic IDs, class names, or content)
    normalized = re.sub(r"\d+", "", normalized)
    # Strip quotes and standard brackets/tags symbols
    # to focus on tags structure and basic attribute names
    normalized = normalized.lower()
    
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

class ElementFingerprint:
    """
    Python model representing the captured state of a DOM element.
    This serves as the core data structure for the selector engine and healing ladder.
    """
    def __init__(self, data: Dict[str, Any]):
        data = data or {}
        self.selectors: List[Dict[str, Any]] = data.get("selectors") or []
        self.tag: str = (data.get("tag") or "").lower()
        self.attributes: Dict[str, Any] = data.get("attributes") or {}
        self.text: str = data.get("text") or ""
        self.context: Dict[str, Any] = data.get("context") or {}
        self.geometry: Dict[str, Any] = data.get("geometry") or {}
        self.visual: Dict[str, Any] = data.get("visual") or {}
        self.navigation: Dict[str, Any] = data.get("navigation") or {}
        self.history: List[Dict[str, Any]] = data.get("history") or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert the fingerprint instance to a serializable dictionary."""
        return {
            "selectors": self.selectors,
            "tag": self.tag,
            "attributes": self.attributes,
            "text": self.text,
            "context": self.context,
            "geometry": self.geometry,
            "visual": self.visual,
            "navigation": self.navigation,
            "history": self.history
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ElementFingerprint":
        """Deserialize from a dictionary representation."""
        return cls(data)

    @property
    def parent_tag(self) -> Optional[str]:
        return self.context.get("parent", {}).get("tag")

    @property
    def parent_classes(self) -> List[str]:
        return self.context.get("parent", {}).get("classes", [])

    @property
    def parent_text(self) -> str:
        return self.context.get("parent", {}).get("text_head", "")

    @property
    def siblings(self) -> List[Dict[str, Any]]:
        return self.context.get("siblings", [])

    @property
    def ancestors(self) -> List[str]:
        return self.context.get("ancestors", [])

    @property
    def index_in_parent(self) -> int:
        return self.context.get("index_in_parent", 0)

    @property
    def child_count(self) -> int:
        return self.context.get("child_count", 0)

    @property
    def x_pct(self) -> float:
        return self.geometry.get("x_pct", 0.0)

    @property
    def y_pct(self) -> float:
        return self.geometry.get("y_pct", 0.0)

    @property
    def width(self) -> float:
        return self.geometry.get("w", 0.0)

    @property
    def height(self) -> float:
        return self.geometry.get("h", 0.0)

    @property
    def dom_neighborhood_hash(self) -> str:
        return self.visual.get("dom_neighborhood_hash", "")


async def capture_from_page(page, element_handle, screenshot_path: Optional[str] = None) -> ElementFingerprint:
    """
    Capture a detailed ElementFingerprint from a live page element using Playwright.
    """
    # Evaluate JavaScript in the context of the element to scrape structured information
    payload = await element_handle.evaluate("""
        (el) => {
            const rect = el.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;
            
            const parent = el.parentElement;
            const parentInfo = parent ? {
                tag: parent.tagName.toLowerCase(),
                classes: Array.from(parent.classList),
                text_head: parent.innerText ? parent.innerText.substring(0, 30).trim() : ""
            } : null;

            const siblings = [];
            let index = 0;
            if (parent) {
                let current = el;
                while ((current = current.previousElementSibling) != null) {
                    index++;
                }
                
                let sibCurrent = parent.firstElementChild;
                let idx = 0;
                while (sibCurrent) {
                    if (sibCurrent !== el && Math.abs(idx - index) <= 2) {
                        siblings.push({
                            tag: sibCurrent.tagName.toLowerCase(),
                            text: sibCurrent.innerText ? sibCurrent.innerText.substring(0, 30).trim() : "",
                            offset: idx - index
                        });
                    }
                    sibCurrent = sibCurrent.nextElementSibling;
                    idx++;
                }
            }

            const ancestors = [];
            let p = el.parentElement;
            while (p && p.tagName && p.tagName.toLowerCase() !== 'body' && p.tagName.toLowerCase() !== 'html') {
                let str = p.tagName.toLowerCase();
                if (p.id) str += '#' + p.id;
                else if (p.classList.length > 0) str += '.' + Array.from(p.classList).join('.');
                ancestors.push(str);
                p = p.parentElement;
            }

            return {
                tag: el.tagName.toLowerCase(),
                text: el.innerText ? el.innerText.trim() : "",
                attributes: Array.from(el.attributes).reduce((acc, a) => ({ ...acc, [a.name]: a.value }), {}),
                geometry: {
                    x: rect.left,
                    y: rect.top,
                    w: rect.width,
                    h: rect.height,
                    viewport: [viewportWidth, viewportHeight],
                    x_pct: parseFloat((rect.left / (viewportWidth || 1)).toFixed(4)),
                    y_pct: parseFloat((rect.top / (viewportHeight || 1)).toFixed(4))
                },
                context: {
                    parent: parentInfo,
                    siblings: siblings,
                    ancestors: ancestors,
                    child_count: el.children.length,
                    index_in_parent: index
                },
                parent_html: parent ? parent.outerHTML.substring(0, 2000) : ""
            };
        }
    """)
    
    # Calculate selector ladder
    from scrapewizard.engine.selector_engine import build_selector_ladder
    selectors = build_selector_ladder(
        payload["tag"],
        payload["attributes"],
        payload["text"],
        payload["context"]
    )
    
    # Compute neighborhood DOM hash
    dom_hash = compute_dom_neighborhood_hash(payload["parent_html"])
    
    # Screenshot
    visual_data = {
        "dom_neighborhood_hash": dom_hash,
    }
    if screenshot_path:
        try:
            await element_handle.screenshot(path=screenshot_path)
            visual_data["screenshot_path"] = screenshot_path
        except Exception as e:
            log(f"Element screenshot failed: {e}", level="warning")
        
    # Navigation context
    frame_url = page.url
    page_obj = getattr(page, "page", page)
    page_title = await page_obj.title() if page_obj else ""
    navigation_data = {
        "url": frame_url,
        "title": page_title
    }
    
    data = {
        "selectors": selectors,
        "tag": payload["tag"],
        "attributes": payload["attributes"],
        "text": payload["text"],
        "context": payload["context"],
        "geometry": payload["geometry"],
        "visual": visual_data,
        "navigation": navigation_data,
        "history": []
    }
    
    return ElementFingerprint(data)
