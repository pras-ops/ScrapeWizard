"""Write a recipe from a page without an LLM.

The builder looks for the repeating block on a page (product cards, table
rows, list entries), works out which values each block holds, names and types
them, and returns a recipe. A recipe is only returned if running it against
the same page really yields records.
"""
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from scrapewizard.engine.selector_engine import is_stable_class, is_stable_id
from scrapewizard.recipe.extract import extract_records, parse
from scrapewizard.recipe.model import Field, Recipe
from scrapewizard.recipe.types import clean_text, infer_type
from scrapewizard.recon.pagination import CSS_SAFE_RE, PaginationDetector

SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "head", "meta", "link", "iframe", "br", "hr", "option"}
# Page furniture: a repeating block inside these is rarely the data.
CHROME_TAGS = {"nav", "header", "footer", "aside"}
CHROME_WORDS = {
    "nav", "navbar", "navigation", "menu", "sidebar", "footer", "header", "breadcrumb",
    "breadcrumbs", "pagination", "pager", "toolbar", "cookie", "banner", "social", "share",
}
HEADING_RE = re.compile(r"(^|[\s>])h[1-6]([.\s>:]|$)")
MIN_ITEMS = 3          # fewer repeats than this is not a list
SAMPLE_SIZE = 12       # items inspected when discovering fields
MIN_COVERAGE = 0.5     # a field must appear in at least half the sampled items
MAX_FIELDS = 12
MAX_TEXT_LENGTH = 500
MAX_CANDIDATES = 200
MAX_ITEM_ELEMENTS = 300  # a block with more elements than this is a page section, not a record
MAX_VALUE_NODES = 80


@dataclass
class BuildResult:
    recipe: Recipe
    records: List[Dict[str, Any]]      # what the recipe yields on the sample page
    next_url: Optional[str] = None     # set when the page links to a next page


@dataclass
class _FieldDraft:
    selectors: List[str]               # the ladder, most specific first
    values: Dict[int, str]             # item index -> value
    position: int                      # order of first appearance in an item
    attr: Optional[str]
    type: str = "text"
    name: str = ""


@dataclass
class _Candidate:
    selector: str
    items: List[Tag]
    fields: List[_FieldDraft]
    score: float


def _classes(tag: Tag) -> List[str]:
    value = tag.get("class") or []
    return value if isinstance(value, list) else str(value).split()


def _stable_classes(tag: Tag) -> List[str]:
    return [c for c in _classes(tag) if CSS_SAFE_RE.match(c) and is_stable_class(c)]


def _simple_selector(tag: Tag, allowed: Optional[set] = None) -> str:
    classes = [c for c in _stable_classes(tag) if allowed is None or c in allowed]
    return tag.name + "".join(f".{c}" for c in classes)


def _same_elements(a: List[Tag], b: List[Tag]) -> bool:
    return len(a) == len(b) and all(x is y for x, y in zip(a, b))


def _anchor_selector(tag: Tag, soup: BeautifulSoup, cache: Dict[str, List[Tag]]) -> Optional[str]:
    """A selector matching exactly this one element, from its id or classes.

    ``cache`` holds earlier lookups: hundreds of sibling blocks ask about the
    same few selectors, and each lookup scans the whole page.
    """
    options = []
    tag_id = tag.get("id")
    if tag_id and CSS_SAFE_RE.match(tag_id) and is_stable_id(tag_id):
        options.append(f"#{tag_id}")
    if _stable_classes(tag):
        options.append(_simple_selector(tag))
    for option in options:
        if option not in cache:
            cache[option] = soup.select(option)
        if _same_elements(cache[option], [tag]):
            return option
    return None


def _candidate_selectors(soup: BeautifulSoup) -> Iterable[Tuple[str, List[Tag]]]:
    """Yield (selector, items) for every repeating block worth inspecting."""
    seen = set()
    anchor_cache: Dict[str, List[Tag]] = {}

    def offer(selector: str, expected: Optional[List[Tag]] = None):
        try:
            items = soup.select(selector)
        except Exception:
            return None
        if len(items) < MIN_ITEMS:
            return None
        if expected is not None and not _same_elements(items, expected):
            return None
        key = tuple(id(i) for i in items)
        if key in seen:
            return None
        seen.add(key)
        return selector, items

    # 1. Elements sharing a class signature anywhere on the page (cards, rows with classes).
    groups: Dict[Tuple[str, Tuple[str, ...]], int] = Counter()
    for tag in soup.find_all(True):
        if tag.name in SKIP_TAGS:
            continue
        classes = _stable_classes(tag)
        if classes:
            groups[(tag.name, tuple(classes))] += 1
    for (name, classes), count in groups.most_common():
        if count < MIN_ITEMS:
            break
        found = offer(name + "".join(f".{c}" for c in classes))
        if found:
            yield found

    # 2. Same-tag siblings without classes (plain <li>, <tr>, <div> lists), anchored on an ancestor.
    for parent in soup.find_all(True):
        if parent.name in SKIP_TAGS:
            continue
        by_name: Dict[str, List[Tag]] = defaultdict(list)
        for child in parent.children:
            if isinstance(child, Tag) and child.name not in SKIP_TAGS and not _stable_classes(child):
                by_name[child.name].append(child)
        for name, children in by_name.items():
            if len(children) < MIN_ITEMS:
                continue
            path = name
            node: Optional[Tag] = parent
            for _ in range(3):  # climb until an ancestor can be named uniquely
                if not isinstance(node, Tag) or node.name in ("html", "[document]"):
                    break
                anchor = _anchor_selector(node, soup, anchor_cache)
                if anchor:
                    found = offer(f"{anchor} > {path}", children)
                    if found:
                        yield found
                    break
                path = f"{node.name} > {path}"
                node = node.parent
            else:
                continue


def _own_text(el: Tag) -> str:
    return clean_text("".join(c for c in el.children if isinstance(c, NavigableString)))


def _value_nodes(item: Tag) -> Iterable[Tuple[Tag, Optional[str], str]]:
    """Yield (element, attribute or None, value) for everything that could be a field."""
    for el in [item, *item.find_all(True)]:
        if el.name in SKIP_TAGS:
            continue
        text = clean_text(el.get_text(" ", strip=True))
        if el.name == "a" and (el.get("href") or "").strip() and not el["href"].startswith(("#", "javascript:")):
            yield el, "href", el["href"].strip()
        if el.name == "img":
            src = (el.get("src") or "").strip()
            lazy = (el.get("data-src") or "").strip()
            if lazy and (not src or src.startswith("data:")):
                yield el, "data-src", lazy
            elif src and not src.startswith("data:"):
                yield el, "src", src
        if el.name == "time" and el.get("datetime"):
            yield el, "datetime", el["datetime"]
        title = clean_text(el.get("title")) if el.name == "a" else ""
        if title:
            yield el, "title", title
            stem = text.rstrip(".\u2026 ").lower()
            if not stem or title.lower().startswith(stem):
                continue  # the visible text is the title, or a cut-off form of it
        if _own_text(el) and len(text) <= MAX_TEXT_LENGTH:
            yield el, None, text


def _relative_selector(item: Tag, el: Tag, common_classes: set) -> str:
    """CSS for ``el`` relative to ``item``: by class if unique, else by position."""
    if el is item:
        return ""
    simple = _simple_selector(el, common_classes)
    if _same_elements(item.select(simple), [el]):
        return simple
    parent = el.parent
    if isinstance(parent, Tag) and parent is not item:
        qualified = f"{_simple_selector(parent, common_classes)} > {simple}"
        if _same_elements(item.select(qualified), [el]):
            return qualified
    parts = []
    node = el
    while node is not item and isinstance(node.parent, Tag):
        same = [c for c in node.parent.children if isinstance(c, Tag) and c.name == node.name]
        index = next(i for i, c in enumerate(same, 1) if c is node)
        parts.append(node.name if len(same) == 1 else f"{node.name}:nth-of-type({index})")
        node = node.parent
    return ":scope > " + " > ".join(reversed(parts))


def _discover_fields(items: List[Tag]) -> List[_FieldDraft]:
    sample = items[:SAMPLE_SIZE]
    if sum(len(item.find_all(True)) for item in sample) > MAX_ITEM_ELEMENTS * len(sample):
        return []  # far too large to be one record; inspecting it is slow and pointless

    # Classes that vary from item to item (state, rating) must not appear in field selectors.
    class_presence: Counter = Counter()
    for item in sample:
        present = set()
        for el in item.find_all(True):
            present.update(_stable_classes(el))
        class_presence.update(present)
    common_classes = {c for c, n in class_presence.items() if n >= MIN_COVERAGE * len(sample)}

    drafts: Dict[Tuple[str, Optional[str]], _FieldDraft] = {}
    for index, item in enumerate(sample):
        for position, (el, attr, value) in enumerate(_value_nodes(item)):
            if position >= MAX_VALUE_NODES:
                break
            selector = _relative_selector(item, el, common_classes)
            key = (selector, attr)
            draft = drafts.get(key)
            if draft is None:
                spec = f"{selector}@{attr}" if attr else selector
                draft = drafts[key] = _FieldDraft(selectors=[spec], values={}, position=position, attr=attr)
            draft.values.setdefault(index, value)

    kept: List[_FieldDraft] = []
    for draft in sorted(drafts.values(), key=lambda d: d.position):
        if len(draft.values) < MIN_COVERAGE * len(sample):
            continue
        distinct = set(draft.values.values())
        if len(distinct) == 1 and len(sample) >= MIN_ITEMS:
            continue  # the same on every item: a label or button, not data
        duplicate = next((k for k in kept if k.values == draft.values), None)
        if duplicate is not None:
            duplicate.selectors.extend(draft.selectors)  # a second route to the same value
            continue
        kept.append(draft)

    kept = [d for d in kept if not _is_shortened_copy(d, kept)]
    kept = _drop_sublists(kept, len(sample))
    kept = [d for d in kept if not _only_adds_boilerplate(d, kept)]

    for draft in kept:
        if draft.attr == "href":
            draft.type = "url"
        elif draft.attr in ("src", "data-src"):
            draft.type = "image"
        elif draft.attr == "datetime":
            draft.type = "date"
        else:
            draft.type = infer_type(list(draft.values.values()))
    return kept[:MAX_FIELDS]


def _is_shortened_copy(draft: _FieldDraft, others: List[_FieldDraft]) -> bool:
    """True if this text is just a cut-off form ("A Light in the ...") of another field."""
    if draft.attr is not None:
        return False
    for other in others:
        if other is draft or other.attr in ("href", "src", "data-src"):
            continue
        shared = [i for i in draft.values if i in other.values]
        if len(shared) < MIN_COVERAGE * len(draft.values):
            continue
        prefixes = 0
        shorter = 0
        for i in shared:
            mine = draft.values[i].rstrip(".… ").lower()
            theirs = other.values[i].lower()
            prefixes += bool(mine) and theirs.startswith(mine)
            shorter += len(draft.values[i]) < len(other.values[i])
        if prefixes >= 0.9 * len(shared) and shorter >= 1:
            return True
    return False


def _drop_sublists(drafts: List[_FieldDraft], sampled: int) -> List[_FieldDraft]:
    """Remove positional fields that are members of a variable-length list.

    Tags, sizes or badges inside a card show up as ``a:nth-of-type(1)``,
    ``(2)``, ``(3)`` with fewer and fewer items having each. They are not
    columns. Table cells, which every row has, are kept.
    """
    families: Dict[Tuple[str, Optional[str]], List[_FieldDraft]] = defaultdict(list)
    for draft in drafts:
        css = draft.selectors[0].split("@")[0]
        if ":nth-of-type(" in css:
            family = re.sub(r":nth-of-type\(\d+\)(?!.*:nth-of-type)", ":nth-of-type(N)", css)
            families[(family, draft.attr)].append(draft)
    dropped = set()
    for members in families.values():
        if len(members) < 2:
            continue
        counts = [len(m.values) for m in members]
        if min(counts) < 0.9 * max(counts) or max(counts) < sampled:
            dropped.update(id(m) for m in members)
    return [d for d in drafts if id(d) not in dropped]


def _only_adds_boilerplate(draft: _FieldDraft, others: List[_FieldDraft]) -> bool:
    """True if this text is another field plus fixed words ("by <author> (about)")."""
    if draft.attr is not None:
        return False
    for other in others:
        if other is draft or other.attr is not None:
            continue
        shared = [i for i in draft.values if i in other.values]
        if len(shared) < max(MIN_ITEMS, int(0.9 * len(draft.values))):
            continue
        leftovers = set()
        for i in shared:
            mine, theirs = draft.values[i], other.values[i]
            if theirs not in mine or theirs == mine:
                break
            leftovers.add(mine.replace(theirs, "", 1))
        else:
            if len(leftovers) == 1:
                return True
    return False


def _class_based_name(selector: str) -> Optional[str]:
    last = re.split(r"[\s>]+", selector.split("@")[0].strip())[-1] if selector.strip() else ""
    classes = re.findall(r"\.([A-Za-z_][\w-]*)", last)
    if not classes:
        return None
    name = re.sub(r"[^a-z0-9]+", "_", classes[-1].lower()).strip("_")
    return name if len(name) >= 2 and not name.isdigit() else None


def _name_fields(fields: List[_FieldDraft], container: str = "") -> None:
    by_type = {"money": "price", "image": "image", "url": "url", "date": "date", "email": "email"}

    def average_length(f: _FieldDraft) -> float:
        return sum(len(v) for v in f.values.values()) / max(len(f.values), 1)

    def title_strength(f: _FieldDraft) -> int:
        """2: a heading or a title attribute. 1: link text. 0: not a title."""
        if f.type != "text" or average_length(f) < 3:
            return 0
        css = f.selectors[0].split("@")[0]
        if f.attr == "title" or HEADING_RE.search(css):
            return 2
        return 1 if re.search(r"(^|[\s>])a([.\s:]|$)", css) else 0

    strongest = max((title_strength(f) for f in fields), default=0)
    title_field = next((f for f in fields if strongest and title_strength(f) == strongest), None)

    unnamed = set()
    for f in fields:
        selector = f.selectors[0]
        if f.type in by_type:
            f.name = by_type[f.type]
            continue
        if f is title_field:
            f.name = "title"
            continue
        from_class = _class_based_name(selector)
        f.name = from_class or ("number" if f.type == "number" else "text")
        if not from_class:
            unnamed.add(id(f))
        # "country_capital" inside a ".country" block reads better as "capital".
        for prefix in re.findall(r"\.([A-Za-z_][\w-]*)", container):
            prefix = re.sub(r"[^a-z0-9]+", "_", prefix.lower()).strip("_") + "_"
            if f.name.startswith(prefix) and len(f.name) - len(prefix) >= 2:
                f.name = f.name[len(prefix):]
                break

    if title_field is None:
        # No heading or link text: call the longest field that has no name of its own the title.
        generic = [f for f in fields if id(f) in unnamed and f.type == "text"]
        if generic:
            max(generic, key=average_length).name = "title"

    used: Counter = Counter()
    for f in fields:
        used[f.name] += 1
        if used[f.name] > 1:
            f.name = f"{f.name}_{used[f.name]}"
    # Title first, then readable values, with long links and image addresses last.
    fields.sort(key=lambda f: (f.name != "title", f.type in ("url", "image"), f.position))


def _in_page_chrome(item: Tag) -> bool:
    node: Optional[Tag] = item
    while isinstance(node, Tag):
        if node.name in CHROME_TAGS:
            return True
        tokens = set()
        for word in _classes(node) + [node.get("id") or "", node.get("role") or ""]:
            tokens.update(re.split(r"[-_\s]+", str(word).lower()))
        if tokens & CHROME_WORDS:
            return True
        node = node.parent
    return False


def _score(items: List[Tag], fields: List[_FieldDraft]) -> float:
    """Higher is better: many items, several well-filled fields, real text."""
    readable = [f for f in fields if f.type not in ("url", "image")]
    if not readable:
        return 0.0
    longest = max(sum(len(v) for v in f.values.values()) / len(f.values) for f in readable)
    if longest < 3:
        return 0.0
    sampled = min(len(items), SAMPLE_SIZE)
    coverage = sum(len(f.values) for f in fields) / (len(fields) * sampled)
    chars = sum(len(v) for f in readable for v in f.values.values()) / sampled
    richness = min(chars, 400) / 400
    score = (min(len(fields), 8) + 2 * richness) * coverage * math.log2(len(items) + 1)
    return score * (0.3 if _in_page_chrome(items[0]) else 1.0)


def _is_wrapper(outer: _Candidate, inner: _Candidate) -> bool:
    """True if each outer item holds several inner items (a row of cards, not a card)."""
    if len(inner.items) < 2 * len(outer.items) or len(inner.fields) < 2:
        return False
    inner_ids = {id(i) for i in inner.items}
    sample = outer.items[:SAMPLE_SIZE]
    wrappers = 0
    for item in sample:
        inside = [d for d in item.find_all(True) if id(d) in inner_ids]
        if len(inside) < 2:
            continue
        total = len(clean_text(item.get_text(" ", strip=True)))
        covered = sum(len(clean_text(d.get_text(" ", strip=True))) for d in inside)
        # A card that merely contains a sub-list (tags, sizes) has plenty of its own text.
        if total and (total - covered) / total < 0.2:
            wrappers += 1
    return wrappers >= 0.5 * len(sample)


def _prefer_inner(chosen: _Candidate, candidates: List[_Candidate]) -> _Candidate:
    """If a block only wraps one equally informative block each, use the inner one.

    ``li.col-xs-6 > article.product_pod``: both give the same records, but the
    inner element is named for what it is and survives layout-grid changes.
    """
    while True:
        chosen_fields = len(chosen.fields)
        inner = None
        for other in candidates:
            if other is chosen or len(other.items) != len(chosen.items) or len(other.fields) < chosen_fields:
                continue
            if all(o is not c and c in o.parents for o, c in zip(other.items, chosen.items)):
                inner = other
                break
        if inner is None:
            return chosen
        chosen = inner


def _matches(items: List[Tag], wanted: str) -> bool:
    wanted = clean_text(wanted).lower()
    for item in items:
        if wanted in clean_text(item.get_text(" ", strip=True)).lower():
            return True
        for el in [item, *item.find_all(True)]:
            for attr in ("title", "alt", "href", "src", "value"):
                if wanted in str(el.get(attr) or "").lower():
                    return True
    return False


def default_name(url: str) -> str:
    """A short file-friendly name from the URL's host: books.toscrape.com -> books."""
    host = (urlparse(url).hostname or "data").lower()
    labels = [label for label in host.split(".") if label and label != "www"]
    if not labels or all(label.isdigit() for label in labels):
        return "data"  # an IP address makes a poor file name
    name = labels[0]
    return re.sub(r"[^a-z0-9_-]+", "_", name).strip("_") or "data"


def _to_recipe(candidate: _Candidate, soup: BeautifulSoup, url: str, name: Optional[str], fetch_mode: str):
    fields = [Field(name=f.name, select=f.selectors, type=f.type) for f in candidate.fields]
    detected = PaginationDetector(soup, url).detect()
    next_url = detected.get("next_url")
    if next_url and detected["type"] == "next_button" and detected.get("selector"):
        pagination: Dict[str, Any] = {"type": "next_link", "select": detected["selector"], "max_pages": 1}
    elif next_url:
        pagination = {"type": "auto", "max_pages": 1}
    else:
        pagination = {"type": "none"}
    recipe = Recipe(
        name=name or default_name(url),
        url=url,
        container=candidate.selector,
        fields=fields,
        fetch=fetch_mode,
        pagination=pagination,
    )
    return recipe, next_url


def build_recipe(
    html: str,
    url: str,
    likes: Optional[List[str]] = None,
    name: Optional[str] = None,
    fetch_mode: str = "http",
) -> Optional[BuildResult]:
    """Build a recipe for the main repeating data on a page.

    Args:
        html: The page source.
        url: Where it came from (used for links and the recipe name).
        likes: Example values the wanted data contains. They pick which list
            on the page is meant and put the matching fields first.
        fetch_mode: Recorded in the recipe: how the page had to be fetched.

    Returns:
        A BuildResult, or None if no repeating data could be found.
    """
    soup = parse(html)
    likes = [like for like in (likes or []) if clean_text(like)]

    candidates: List[_Candidate] = []
    for selector, items in _candidate_selectors(soup):
        if len(candidates) >= MAX_CANDIDATES:
            break
        fields = _discover_fields(items)
        if not fields:
            continue
        score = _score(items, fields)
        if score > 0:
            candidates.append(_Candidate(selector, items, fields, score))
    if not candidates:
        return None

    if likes:
        hits = {id(c): sum(1 for like in likes if _matches(c.items, like)) for c in candidates}
        best = max(hits.values())
        if best == 0:
            return None  # nothing on the page contains the example values
        candidates = [c for c in candidates if hits[id(c)] == best]

    candidates.sort(key=lambda c: c.score, reverse=True)
    leaders = candidates[:8]
    ranked = [c for c in candidates if not any(_is_wrapper(c, other) for other in leaders if other is not c)]

    ordered = ranked or candidates
    ordered = [_prefer_inner(ordered[0], candidates)] + ordered
    for candidate in ordered:
        _name_fields(candidate.fields, candidate.selector)
        if likes:
            wanted = [clean_text(like).lower() for like in likes]
            candidate.fields.sort(
                key=lambda f: not any(w in v.lower() for w in wanted for v in f.values.values())
            )
        recipe, next_url = _to_recipe(candidate, soup, url, name, fetch_mode)
        # Accept the recipe only if it really works on the page it was built from.
        records = extract_records(soup, recipe, url)
        if len(records) < MIN_ITEMS:
            continue
        well_filled = [
            f.name for f in recipe.fields
            if f.type not in ("url", "image")
            and sum(1 for r in records if r.get(f.name) is not None) >= 0.95 * len(records)
        ]
        recipe.checks = {"min_records": max(1, len(records) // 2), "required": well_filled[:2]}
        return BuildResult(recipe=recipe, records=records, next_url=next_url)
    return None
