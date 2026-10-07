"""Item pages: learn which extra fields each item's own page holds.

A list shows a summary of each item. ``build_detail_fields`` looks at a few
item pages and returns fields for what they add: labelled rows ("UPC | a897…"),
structured data the page embeds (JSON-LD), the main heading and the
description. The fields are stored in the recipe and read on every run.
"""
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

from scrapewizard.engine.selector_engine import is_stable_class, is_stable_id
from scrapewizard.recipe.extract import jsonld_objects, read_document_value
from scrapewizard.recipe.model import Field
from scrapewizard.recipe.types import clean_text, infer_type
from scrapewizard.recon.pagination import CSS_SAFE_RE

MAX_DETAIL_FIELDS = 20
MAX_LABEL_LENGTH = 40
MAX_VALUE_LENGTH = 300
MIN_DESCRIPTION_LENGTH = 150
# Structured-data blocks that describe the site or its navigation, not the item.
SKIPPED_JSONLD_TYPES = {
    "BreadcrumbList", "WebSite", "Organization", "WebPage", "SearchAction", "ItemList",
    "ListItem", "ImageObject", "SiteNavigationElement", "WPHeader", "WPFooter",
}
CHROME_TAGS = {"nav", "header", "footer", "aside", "script", "style", "form"}


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _same_value(a: Any, b: Any) -> bool:
    """True if two values say the same thing: equal text, or the same amount ("$2.99" and "2.99")."""
    a, b = clean_text(a).lower(), clean_text(b).lower()
    if a == b:
        return True
    digits_a, digits_b = re.sub(r"[^\d.,]", "", a), re.sub(r"[^\d.,]", "", b)
    # Only amounts: text with words around a number is not the same as the bare number.
    is_amount = lambda text, digits: digits and len(text) - len(digits) <= 4  # noqa: E731
    return bool(digits_a) and digits_a == digits_b and is_amount(a, digits_a) and is_amount(b, digits_b)


def _unique(soup: BeautifulSoup, selector: str) -> bool:
    try:
        return len(soup.select(selector)) == 1
    except Exception:
        return False


def _labelled_rows(soup: BeautifulSoup) -> List[Tuple[str, str, str]]:
    """(name, selector, source) for every "label | value" pair in tables and definition lists."""
    found = []
    pairs: List[Tuple[Tag, Tag]] = []
    for row in soup.find_all("tr"):
        cells = [c for c in row.find_all(["th", "td"], recursive=False)]
        if len(cells) == 2:
            pairs.append((cells[0], cells[1]))
    for term in soup.find_all("dt"):
        definition = term.find_next_sibling()
        if definition is not None and definition.name == "dd":
            pairs.append((term, definition))

    for label_cell, value_cell in pairs:
        label = clean_text(label_cell.get_text(" ", strip=True)).rstrip(":").strip()
        value = clean_text(value_cell.get_text(" ", strip=True))
        if not label or len(label) > MAX_LABEL_LENGTH or not value or len(value) > MAX_VALUE_LENGTH:
            continue
        if '"' in label or "\\" in label or not _slug(label):
            continue
        selector = f'{label_cell.name}:-soup-contains("{label}") + {value_cell.name}'
        if _unique(soup, selector):
            found.append((_slug(label), selector, "row"))
    return found


def _jsonld_leaves(node: Dict[str, Any], prefix: str = "", depth: int = 0) -> List[Tuple[str, Any]]:
    leaves = []
    for key, value in node.items():
        if key.startswith("@"):
            continue
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, dict):
            if depth < 2:
                leaves.extend(_jsonld_leaves(value, path, depth + 1))
        elif isinstance(value, (str, int, float)) and not isinstance(value, bool) and clean_text(value):
            leaves.append((path, value))
    return leaves


def _jsonld_fields(soup: BeautifulSoup) -> List[Tuple[str, str, str]]:
    found = []
    for node in jsonld_objects(soup):
        kinds = node.get("@type")
        kinds = kinds if isinstance(kinds, list) else [kinds]
        if any(k in SKIPPED_JSONLD_TYPES for k in kinds):
            continue
        for path, _ in _jsonld_leaves(node):
            parts = path.split(".")
            # "offers.price" reads better as "price"; "author.name" must stay "author_name".
            name = parts[-1] if len(parts) == 1 or parts[-1] not in ("name", "url", "value", "@id") else "_".join(parts[-2:])
            found.append((_slug(re.sub(r"(?<=[a-z])(?=[A-Z])", "_", name)), f"jsonld:{path}", "jsonld"))
    return found


def _selector_for_block(el: Tag, soup: BeautifulSoup) -> Optional[str]:
    """A selector for one text block: its own id or class, or its place after a named neighbour."""
    el_id = el.get("id")
    if el_id and CSS_SAFE_RE.match(el_id) and is_stable_id(el_id) and _unique(soup, f"#{el_id}"):
        return f"#{el_id}"
    classes = [c for c in (el.get("class") or []) if CSS_SAFE_RE.match(c) and is_stable_class(c)]
    if classes:
        selector = el.name + "".join(f".{c}" for c in classes)
        if _unique(soup, selector):
            return selector
    previous = el.find_previous_sibling()
    if previous is not None:
        prev_id = previous.get("id")
        if prev_id and CSS_SAFE_RE.match(prev_id) and is_stable_id(prev_id):
            selector = f"#{prev_id} + {el.name}"
            if _unique(soup, selector):
                return selector
    return None


def _description(soup: BeautifulSoup) -> Optional[Tuple[str, str, str]]:
    """The longest block of running text on the page, if it can be selected reliably."""
    best: Optional[Tag] = None
    best_length = MIN_DESCRIPTION_LENGTH
    for el in soup.find_all(["p", "div", "section", "article"]):
        if any(parent.name in CHROME_TAGS for parent in el.parents):
            continue
        own = clean_text("".join(c for c in el.children if isinstance(c, str)))
        if len(own) >= best_length:
            best, best_length = el, len(own)
    if best is None:
        return None
    selector = _selector_for_block(best, soup)
    return ("description", selector, "text") if selector else None


def _page_fields(soup: BeautifulSoup) -> List[Tuple[str, str, str]]:
    fields = _labelled_rows(soup)
    if len(soup.find_all("h1")) == 1:
        fields.append(("heading", "h1", "heading"))
    fields.extend(_jsonld_fields(soup))
    description = _description(soup)
    if description:
        fields.append(description)
    elif read_document_value(soup, "meta:description"):
        fields.append(("description", "meta:description", "meta"))
    return fields


def build_detail_fields(
    pages: List[BeautifulSoup],
    list_records: List[Dict[str, Any]],
    taken_names: List[str],
) -> List[Field]:
    """Fields that item pages add to what the list already gives.

    Args:
        pages: Parsed item pages, in the same order as ``list_records``.
        list_records: The list's record for each of those pages. A value the
            list already holds is not collected a second time.
        taken_names: Field names already used by the list.
    """
    if not pages:
        return []
    order: List[str] = []
    specs: Dict[str, Tuple[str, str]] = {}      # selector -> (name, source)
    values: Dict[str, Dict[int, str]] = {}      # selector -> page index -> value
    for index, soup in enumerate(pages):
        for name, selector, source in _page_fields(soup):
            value = read_document_value(soup, selector)
            if not value:
                continue
            if selector not in specs:
                specs[selector] = (name, source)
                values[selector] = {}
                order.append(selector)
            values[selector].setdefault(index, value)

    needed = max(1, math.ceil(0.6 * len(pages)))
    kept: List[str] = []
    for selector in order:
        found = values[selector]
        name, source = specs[selector]
        if len(found) < needed:
            continue
        # Already known from the list (the heading is usually the list's title).
        if all(any(_same_value(v, x) for x in list_records[i].values() if x is not None)
               for i, v in found.items()):
            continue
        # The same on every page and not a labelled row: site-wide text, not item data.
        if source != "row" and len(pages) >= 3 and len(set(found.values())) == 1:
            continue
        if any(values[other] == found for other in kept):
            continue  # a second route to a value already kept
        kept.append(selector)

    fields: List[Field] = []
    used = set(taken_names)
    for selector in kept[:MAX_DETAIL_FIELDS]:
        name, _ = specs[selector]
        base, n = name, 2
        if name in used:
            name = f"{base}_detail"  # the item page's fuller version of a list field
        while name in used:
            name, n = f"{base}_{n}", n + 1
        used.add(name)
        fields.append(Field(name=name, select=[selector], type=infer_type(list(values[selector].values()))))
    return fields
