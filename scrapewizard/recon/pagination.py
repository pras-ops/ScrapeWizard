import re
from typing import Any, Dict, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

# Link text that means "go to the next page".
NEXT_TEXTS = {
    "next", "next page", "next »", "next ›", "next →", "next >",
    "older", "older posts", "older entries",
    ">", ">>", "›", "»", "→",
}
PREV_TEXTS = {"<", "<<", "‹", "«", "←"}
PREV_RE = re.compile(r"\b(prev|previous|back|newer)\b", re.I)
LOAD_MORE_RE = re.compile(r"^(load|show|view|see)\s+more\b|^more results\b", re.I)
NEXT_CLASS_RE = re.compile(r"(^|[-_])next($|[-_])", re.I)
CURRENT_CLASSES = {"active", "current", "selected", "is-active", "is-current"}
# A class or id is only used in a selector if it needs no CSS escaping.
CSS_SAFE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def _text(tag: Tag) -> str:
    return " ".join(tag.get_text(" ", strip=True).split()).lower()


def _classes(tag: Optional[Tag]) -> list:
    if tag is None:
        return []
    value = tag.get("class") or []
    return value if isinstance(value, list) else str(value).split()


def _usable_href(tag: Tag) -> Optional[str]:
    href = (tag.get("href") or "").strip()
    if not href or href.startswith("#") or href.lower().startswith("javascript:"):
        return None
    return href


def _is_next_link(tag: Tag) -> bool:
    """True if an <a> looks like a 'next page' link."""
    rel = tag.get("rel") or []
    rel = rel if isinstance(rel, list) else str(rel).split()
    if any(r.lower() == "next" for r in rel):
        return True
    text = _text(tag)
    label = f"{tag.get('aria-label') or ''} {tag.get('title') or ''}".lower()
    # A "previous" link can sit inside a wrapper whose class mentions "next".
    if PREV_RE.search(text) or PREV_RE.search(label) or text in PREV_TEXTS:
        return False
    if text in NEXT_TEXTS:
        return True
    if re.search(r"\bnext\b", label):
        return True
    # Icon-only links are often marked by a class on the link or its wrapper.
    own_and_parent = _classes(tag) + _classes(tag.parent if isinstance(tag.parent, Tag) else None)
    return any(NEXT_CLASS_RE.search(c) for c in own_and_parent)


def css_for(tag: Tag, soup: BeautifulSoup) -> Optional[str]:
    """Build a valid CSS selector that matches exactly this tag, or None."""
    candidates = []
    tag_id = tag.get("id")
    if tag_id and CSS_SAFE_RE.match(tag_id):
        candidates.append(f"#{tag_id}")
    rel = tag.get("rel") or []
    rel = rel if isinstance(rel, list) else str(rel).split()
    if any(r.lower() == "next" for r in rel):
        candidates.append(f'{tag.name}[rel~="next"]')
    safe = [c for c in _classes(tag) if CSS_SAFE_RE.match(c)]
    if safe:
        candidates.append(tag.name + "".join(f".{c}" for c in safe))
    parent = tag.parent if isinstance(tag.parent, Tag) else None
    parent_safe = [c for c in _classes(parent) if CSS_SAFE_RE.match(c)]
    if parent is not None and parent_safe:
        candidates.append(f"{parent.name}{''.join(f'.{c}' for c in parent_safe)} > {tag.name}")

    for selector in candidates:
        try:
            matches = soup.select(selector)
        except Exception:
            continue
        if len(matches) == 1 and matches[0] is tag:
            return selector
    return None


def _find_next_link(soup: BeautifulSoup) -> Optional[Tag]:
    for tag in soup.find_all("a"):
        if _usable_href(tag) and _is_next_link(tag):
            return tag
    return None


def _find_numbered_next(soup: BeautifulSoup) -> Optional[Tag]:
    """Find the link for (current page + 1) next to a marked current page."""
    for marker in soup.find_all(True):
        is_current = marker.get("aria-current") in ("page", "true") or (
            set(c.lower() for c in _classes(marker)) & CURRENT_CLASSES
        )
        if not is_current:
            continue
        label = _text(marker)
        if not label.isdigit():
            continue
        wanted = str(int(label) + 1)
        scope = marker.parent
        for _ in range(3):  # look a few levels up for the sibling page links
            if not isinstance(scope, Tag):
                break
            for link in scope.find_all("a"):
                if _usable_href(link) and _text(link) == wanted:
                    return link
            scope = scope.parent
    return None


def _find_load_more(soup: BeautifulSoup) -> Optional[Tag]:
    for tag in soup.find_all(["button", "a"]):
        if LOAD_MORE_RE.search(_text(tag)):
            return tag
    return None


def find_next_url(soup: BeautifulSoup, url: str) -> Optional[str]:
    """Return the absolute URL of the next page, or None if there isn't one."""
    head_link = soup.find("link", rel=lambda v: v and "next" in (v if isinstance(v, list) else str(v).split()))
    link = _find_next_link(soup) or _find_numbered_next(soup)
    href = _usable_href(link) if link is not None else None
    if href is None and head_link is not None:
        href = _usable_href(head_link)
    if href is None:
        return None
    next_url = urljoin(url, href)
    return None if next_url == url else next_url


class PaginationDetector:
    """
    Detects pagination mechanisms on a page.
    """

    def __init__(self, soup: BeautifulSoup, url: str):
        self.soup = soup
        self.url = url

    def detect(self) -> Dict[str, Any]:
        """Run detection heuristics.

        Returns a dict with ``detected`` and ``type``. Types:
        ``next_button`` (a link to the next page), ``numbered`` (page-number
        links with the current page marked), ``load_more`` (a button that
        appends results), ``url_param`` (guessed from the URL) or ``none``.
        Any ``selector`` returned is valid CSS matching exactly one element.
        """
        next_link = _find_next_link(self.soup)
        if next_link is not None:
            return {
                "detected": True,
                "type": "next_button",
                "selector": css_for(next_link, self.soup),
                "next_url": urljoin(self.url, _usable_href(next_link)),
            }

        numbered = _find_numbered_next(self.soup)
        if numbered is not None:
            return {
                "detected": True,
                "type": "numbered",
                "selector": css_for(numbered, self.soup),
                "next_url": urljoin(self.url, _usable_href(numbered)),
            }

        load_more = _find_load_more(self.soup)
        if load_more is not None:
            return {
                "detected": True,
                "type": "load_more",
                "selector": css_for(load_more, self.soup),
            }

        if "page=" in self.url or "/p/" in self.url:
            return {
                "detected": True,
                "type": "url_param",
                "param": "guessed_from_url",
            }

        return {"detected": False, "type": "none"}
