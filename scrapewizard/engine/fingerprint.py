import hashlib
import re
from typing import Dict, List, Any, Optional
from pathlib import Path

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
        self.selectors: List[Dict[str, Any]] = data.get("selectors", [])
        self.tag: str = data.get("tag", "").lower()
        self.attributes: Dict[str, Any] = data.get("attributes", {})
        self.text: str = data.get("text", "")
        self.context: Dict[str, Any] = data.get("context", {})
        self.geometry: Dict[str, Any] = data.get("geometry", {})
        self.visual: Dict[str, Any] = data.get("visual", {})
        self.navigation: Dict[str, Any] = data.get("navigation", {})
        self.history: List[Dict[str, Any]] = data.get("history", [])

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
