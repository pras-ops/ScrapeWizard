"""Write a recipe from a page without an LLM.

The builder looks for the repeating block on a page (product cards, table
rows, list entries), works out which values each block holds, names and types
them, and returns a recipe. A recipe is only returned if running it against
the same page really yields records.
"""
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag

from scrapewizard.engine.selector_engine import is_stable_class, is_stable_id
from scrapewizard.recipe.embedded import find_lists
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
# "subnav", "topnav", "navbar", "main-menu" and the like.
CHROME_TOKEN_RE = re.compile(r"^(?:(?:sub|top|main|side|site|global|primary|footer)?nav(?:bar|igation)?|\w*menu)$")
VOWELS = set("aeiouy")
# A value in a table cell, addressed from its row: ":scope > td:nth-of-type(3)" or deeper inside that cell.
TABLE_CELL_RE = re.compile(r"^:scope > (t[dh](?::nth-of-type\(\d+\))?)(?= |$)")
TABLE_CELL_ONLY_RE = re.compile(r"^:scope > t[dh]:nth-of-type\(\d+\)$")
HEADING_RE = re.compile(r"(^|[\s>])h[1-6]([.\s>:\[]|$)")
MIN_ITEMS = 3          # fewer repeats than this is not a list
SAMPLE_SIZE = 12       # items inspected when discovering fields
MIN_COVERAGE = 0.5     # a field must appear in at least half the sampled items
MAX_FIELDS = 12        # columns in a finished recipe
DISCOVERED_FIELDS = 24 # fields kept while blocks are still being compared with each other
# Words in a class name that say what a value is. A class containing one is preferred as the field's name.
FIELD_WORDS = (
    "title", "name", "author", "price", "date", "time", "summary", "description", "subject",
    "rating", "score", "comment", "category", "tag", "location", "company", "salary", "status",
)
MAX_TEXT_LENGTH = 500
MAX_CANDIDATES = 200
# A value repeated on every item is kept only if it is not one of these controls ...
CONTROL_TAGS = {"a", "button", "label", "input", "select", "summary"}
# ... and its class says what it is, rather than being one of these generic words.
GENERIC_CLASS_NAMES = {"label", "caption", "prefix", "suffix", "icon", "btn", "button", "link", "heading", "header", "text"}
MAX_ITEM_ELEMENTS = 300  # a block with more elements than this is a page section, not a record
MAX_VALUE_NODES = 80


@dataclass
class BuildResult:
    recipe: Recipe
    records: List[Dict[str, Any]]      # what the recipe yields on the sample page
    next_url: Optional[str] = None     # set when the page links to a next page
    in_menu: bool = False              # the list sits in navigation, a header or a footer

    @property
    def has_more(self) -> bool:
        """True if the list continues: on another page, or by loading more in place."""
        return self.next_url is not None or self.recipe.pagination.get("type") in ("load_more", "scroll")


@dataclass
class _FieldDraft:
    selectors: List[str]               # the ladder, most specific first
    values: Dict[int, str]             # item index -> value
    position: int                      # order of first appearance in an item
    attr: Optional[str]
    tag: str = ""                      # tag of the element the value was read from
    type: str = "text"
    name: str = ""
    hints: Dict[str, Counter] = field(default_factory=dict)   # kind of hint -> the words seen, per item


@dataclass
class _Candidate:
    selector: str
    items: List[Tag]
    fields: List[_FieldDraft]
    score: float
    partners: Optional[List[Optional[Tag]]] = None   # element after each item, for paired layouts


def _classes(tag: Tag) -> List[str]:
    value = tag.get("class") or []
    return value if isinstance(value, list) else str(value).split()


# Attributes a site puts on elements for its own tests or for search engines. They say what an
# element is and survive a restyle, which the class names of a component library do not.
HOOK_ATTRIBUTES = ("data-testid", "data-test", "data-test-id", "data-qa", "data-cy", "itemprop")
TOKEN_RE = re.compile(r'\.[A-Za-z_][\w-]*|\[[a-z-]+="[^"\]]*"\]')
HOOK_RE = re.compile(r'\[([a-z-]+)="([^"\]]*)"\]')
CAMEL_WORD_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+|\d+")


def _hooks(tag: Tag) -> List[str]:
    """``[data-testid="card-headline"]`` for each usable hook attribute on the element."""
    found = []
    for name in HOOK_ATTRIBUTES:
        value = tag.get(name)
        if isinstance(value, str) and CSS_SAFE_RE.match(value) and not re.search(r"\d{3,}", value):
            found.append(f'[{name}="{value}"]')
    return found


def _tokens(tag: Tag) -> List[str]:
    """Everything a selector for this element may test: its classes and its hooks."""
    return _classes(tag) + _hooks(tag)


def _is_hashed_class(class_name: str) -> bool:
    """True for short mixed-case names a build tool made up: ``jeApUG``, ``dyeGOh``, ``ewmvhB``.

    They change at the site's next release, so a selector must not rest on them.
    Real camelCase (``navBar``, ``productCard``) has few, long words.
    """
    if not 5 <= len(class_name) <= 8 or not class_name.isalnum():
        return False
    if class_name.islower() or class_name.isupper() or not any(c.isupper() for c in class_name[1:]):
        return False
    words = CAMEL_WORD_RE.findall(class_name)
    return len(words) >= 3 or any(w.isupper() and len(w) >= 2 for w in words) or class_name[-1].isupper()


def _stable_classes(tag: Tag) -> List[str]:
    """The tokens a selector can safely use: lasting classes, then hooks."""
    classes = [c for c in _classes(tag) if CSS_SAFE_RE.match(c) and is_stable_class(c) and not _is_hashed_class(c)]
    return classes + _hooks(tag)


def _css(name: str, tokens: Iterable[str]) -> str:
    return name + "".join(t if t.startswith("[") else f".{t}" for t in tokens)


def _simple_selector(tag: Tag, allowed: Optional[set] = None) -> str:
    return _css(tag.name, [c for c in _stable_classes(tag) if allowed is None or c in allowed])


def _same_elements(a: List[Tag], b: List[Tag]) -> bool:
    return len(a) == len(b) and all(x is y for x, y in zip(a, b))


def _tag_index(root: Tag) -> Dict[str, List[Tuple[Tag, frozenset]]]:
    """Every element under ``root`` by tag name, with its classes, for fast uniqueness checks."""
    index: Dict[str, List[Tuple[Tag, frozenset]]] = defaultdict(list)
    for el in root.find_all(True):
        index[el.name].append((el, frozenset(_tokens(el))))
    return index


class _PageIndex:
    """Every element of the page by tag name and by id, built in one pass.

    "Which elements does ``li.card`` select?" and "is ``#results`` unique?" are
    asked hundreds of times while looking for lists. Answering from this index
    is a lookup; asking the selector engine is a scan of the whole page each time,
    which on a large page (a long Wikipedia table) took most of a minute in total.
    """

    def __init__(self, soup: BeautifulSoup):
        self.by_tag = _tag_index(soup)
        self.id_count: Counter = Counter()
        for members in self.by_tag.values():
            for el, _ in members:
                if el.get("id"):
                    self.id_count[el["id"]] += 1
        self._unique: Dict[Tuple[str, frozenset], bool] = {}

    def select(self, name: str, classes: Iterable[str]) -> List[Tag]:
        """What ``name.class1.class2`` selects, in page order."""
        wanted = frozenset(classes)
        return [el for el, has in self.by_tag.get(name, ()) if wanted <= has]

    def is_only(self, name: str, classes: Iterable[str]) -> bool:
        key = (name, frozenset(classes))
        if key not in self._unique:
            self._unique[key] = len(self.select(name, key[1])) == 1
        return self._unique[key]


def _anchor_selector(tag: Tag, index: _PageIndex) -> Optional[str]:
    """A selector matching exactly this one element, from its id or classes."""
    tag_id = tag.get("id")
    if tag_id and CSS_SAFE_RE.match(tag_id) and is_stable_id(tag_id) and index.id_count[tag_id] == 1:
        return f"#{tag_id}"
    classes = _stable_classes(tag)
    if classes and index.is_only(tag.name, classes):
        return _simple_selector(tag)
    if tag.name == "body":
        return "body"  # a page with no ids or classes at all still has one body
    return None


def _candidate_selectors(soup: BeautifulSoup) -> Iterable[Tuple[str, List[Tag]]]:
    """Yield (selector, items) for every repeating block worth inspecting."""
    seen = set()
    index = _PageIndex(soup)

    def offer(name: str, classes: Tuple[str, ...]):
        items = index.select(name, classes)
        if len(items) < MIN_ITEMS:
            return None
        key = tuple(id(i) for i in items)
        if key in seen:
            return None
        seen.add(key)
        return _css(name, classes), items

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
        found = offer(name, classes)
        if found:
            yield found

    # 1b. Hooks that differ only in a leading word: "dundee-card", "london-card" and
    #     "chester-card" are all cards, laid out differently. Together they are the list.
    families: Dict[Tuple[str, str, str], set] = defaultdict(set)
    for name, members in index.by_tag.items():
        if name in SKIP_TAGS:
            continue
        for tag, _ in members:
            for attr in HOOK_ATTRIBUTES:
                value = tag.get(attr)
                if isinstance(value, str) and CSS_SAFE_RE.match(value) and "-" in value:
                    families[(name, attr, value.rsplit("-", 1)[1])].add(value)
    for (name, attr, ending), values in families.items():
        if len(values) < 2 or not ending.isalpha():
            continue
        items = [tag for tag, _ in index.by_tag[name]
                 if isinstance(tag.get(attr), str) and tag[attr].endswith(f"-{ending}")]
        key = tuple(id(i) for i in items)
        if len(items) >= MIN_ITEMS and key not in seen:
            seen.add(key)
            yield f'{name}[{attr}$="-{ending}"]', items

    # 2. Same-tag siblings (plain <li>, <tr>, <div> lists), reached from an ancestor that can be named.
    #    All siblings of a tag form one group whether or not some carry a class: the rows of a
    #    table are its records even when a few are marked "total" or "highlight".
    for parent in soup.find_all(True):
        if parent.name in SKIP_TAGS:
            continue
        by_name: Dict[str, List[Tag]] = defaultdict(list)
        for child in parent.children:
            if isinstance(child, Tag) and child.name not in SKIP_TAGS:
                by_name[child.name].append(child)
        for name, children in by_name.items():
            if len(children) < MIN_ITEMS:
                continue
            key = tuple(id(c) for c in children)
            if key in seen:
                continue  # the same elements were already found by their class
            plain_steps = [name]
            exact_steps = [name]
            node: Optional[Tag] = parent
            for _ in range(6):  # climb until an ancestor can be named uniquely
                if not isinstance(node, Tag) or node.name in ("html", "[document]"):
                    break
                anchor = _anchor_selector(node, index)
                if anchor:
                    # The short path first. If the page has look-alike blocks (several tables with
                    # the same classes), the path with positions picks out exactly this one.
                    # The path is checked by walking child steps from the anchor: asking the
                    # selector engine instead costs a scan of the anchor's whole subtree per group.
                    for steps in (plain_steps, exact_steps):
                        if _same_elements(_follow_steps(node, steps), children):
                            seen.add(key)
                            yield f"{anchor} > {' > '.join(steps)}", children
                            break
                    break
                plain_steps = [node.name] + plain_steps
                exact_steps = [_positional_step(node)] + exact_steps
                node = node.parent


def _follow_steps(start: Tag, steps: List[str]) -> List[Tag]:
    """The elements ``start > step > step ...`` selects, found by walking direct children."""
    current = [start]
    for step in steps:
        name, _, position = step.partition(":nth-of-type(")
        found: List[Tag] = []
        for node in current:
            same = [c for c in node.children if isinstance(c, Tag) and c.name == name]
            found.extend(same[int(position[:-1]) - 1:int(position[:-1])] if position else same)
        current = found
    return current


def _positional_step(node: Tag) -> str:
    """``table`` if it is its parent's only table, else ``table:nth-of-type(2)``."""
    if not isinstance(node.parent, Tag):
        return node.name
    same = [c for c in node.parent.children if isinstance(c, Tag) and c.name == node.name]
    return node.name if len(same) == 1 else f"{node.name}:nth-of-type({next(i for i, c in enumerate(same, 1) if c is node)})"


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
            continue  # its visible text is the same date written another way
        title = clean_text(el.get("title")) if el.name == "a" else ""
        if title:
            yield el, "title", title
            stem = text.rstrip(".\u2026 ").lower()
            if not stem or title.lower().startswith(stem):
                continue  # the visible text is the title, or a cut-off form of it
        if _own_text(el) and len(text) <= MAX_TEXT_LENGTH:
            yield el, None, text


def _element_hints(el: Tag) -> Dict[str, str]:
    """Words on or around an element that say what its value is, for when no class does.

    ``href``: the last part of a link's address (``/owner/repo/stargazers``).
    ``icon``: the label of an icon inside it. ``aria``: its own accessible label.
    Only a hint that is the same on every item is used as a name.
    """
    hints: Dict[str, str] = {}
    if el.name == "a":
        parts = [part for part in urlsplit(el.get("href") or "").path.split("/") if part]
        if len(parts) >= 2:  # one part ("/login") is the same link on every item, not a kind of link
            hints["href"] = parts[-1]
    icon = el.find(["svg", "img", "i"])
    if icon is not None:
        word = clean_text(icon.get("aria-label") or icon.get("alt") or icon.get("title"))
        if word:
            hints["icon"] = word
    label = clean_text(el.get("aria-label"))
    if label:
        hints["aria"] = label
    return hints


def _relative_selector(item: Tag, el: Tag, common_classes: set,
                       index: Optional[Dict[str, List[Tuple[Tag, frozenset]]]] = None) -> str:
    """CSS for ``el`` relative to ``item``: by class if unique, else by position.

    ``index`` (from ``_tag_index(item)``) lets "is this selector unique within
    the item?" be answered by counting, instead of running the selector engine
    over the item for every value in it.
    """
    if el is item:
        return ""
    index = index if index is not None else _tag_index(item)

    def wanted(tag: Tag) -> frozenset:
        return frozenset(c for c in _stable_classes(tag) if c in common_classes)

    def matching(tag_name: str, classes: frozenset) -> List[Tag]:
        # What "tag.class1.class2" selects: same tag, at least those classes.
        return [other for other, has in index.get(tag_name, ()) if classes <= has]

    simple = _simple_selector(el, common_classes)
    same_kind = matching(el.name, wanted(el))
    if len(same_kind) == 1:
        return simple
    parent = el.parent
    if isinstance(parent, Tag) and parent is not item:
        parent_classes = wanted(parent)
        # The item itself may be the matching parent: a selector run on the item sees it too.
        with_parent = [
            other for other in same_kind
            if isinstance(other.parent, Tag)
            and other.parent.name == parent.name and parent_classes <= frozenset(_tokens(other.parent))
        ]
        if len(with_parent) == 1:
            return f"{_simple_selector(parent, common_classes)} > {simple}"
    parts = []
    node = el
    while node is not item and isinstance(node.parent, Tag):
        same = [c for c in node.parent.children if isinstance(c, Tag) and c.name == node.name]
        index = next(i for i, c in enumerate(same, 1) if c is node)
        parts.append(node.name if len(same) == 1 else f"{node.name}:nth-of-type({index})")
        node = node.parent
    return ":scope > " + " > ".join(reversed(parts))


def _partners(items: List[Tag]) -> Optional[List[Optional[Tag]]]:
    """The element right after each item, when records come as pairs.

    Some pages split one record over two neighbours: ``dt`` then ``dd``, or a
    title row then a details row. Returns the partner of every item, or None
    if the items are not laid out that way.

    The item must hold text of its own. Otherwise an empty spacer between
    records would qualify as "the item", with the real record as its partner.
    """
    item_ids = {id(i) for i in items}

    def partner_of(item: Tag) -> Optional[Tag]:
        sibling = item.find_next_sibling()
        usable = (
            isinstance(sibling, Tag)
            and id(sibling) not in item_ids
            and sibling.name not in SKIP_TAGS
            and clean_text(sibling.get_text(" ", strip=True))
            and len(sibling.find_all(True)) <= MAX_ITEM_ELEMENTS
            and not any(id(d) in item_ids for d in sibling.find_all(True))
        )
        return sibling if usable else None

    sample = items[:SAMPLE_SIZE]
    if sum(1 for item in sample if clean_text(item.get_text(" ", strip=True))) < 0.8 * len(sample):
        return None
    sampled = [partner_of(item) for item in sample]
    present = [partner for partner in sampled if partner is not None]
    if len(present) < 0.8 * len(sample) or len({partner.name for partner in present}) != 1:
        return None
    # In "dt dd dt dd", each dd is followed by a dt, but that dt starts the NEXT record.
    # If something of the partner's kind comes before the first item, the items are second halves.
    before = items[0].find_previous_sibling()
    if isinstance(before, Tag) and id(before) not in item_ids and before.name == present[0].name \
            and before.name != items[0].name:
        return None
    return sampled + [partner_of(item) for item in items[SAMPLE_SIZE:]]


def _discover_fields(items: List[Tag], partners: Optional[List[Optional[Tag]]] = None) -> List[_FieldDraft]:
    sample = items[:SAMPLE_SIZE]
    if sum(len(item.find_all(True)) for item in sample) > MAX_ITEM_ELEMENTS * len(sample):
        return []  # far too large to be one record; inspecting it is slow and pointless

    # Classes that vary from item to item (state, rating) must not appear in field selectors.
    class_presence: Counter = Counter()
    for index, item in enumerate(sample):
        present = set()
        roots = [item] + ([partners[index]] if partners and partners[index] is not None else [])
        for root in roots:
            for el in root.find_all(True):
                present.update(_stable_classes(el))
        class_presence.update(present)
    common_classes = {c for c, n in class_presence.items() if n >= MIN_COVERAGE * len(sample)}

    drafts: Dict[Tuple[str, Optional[str]], _FieldDraft] = {}
    for index, item in enumerate(sample):
        # The item itself, then its partner. "+" in a selector means "in the element after the item".
        roots = [(item, "")]
        if partners and partners[index] is not None:
            roots.append((partners[index], "+"))
        position = 0
        for root, prefix in roots:
            index_of_root = _tag_index(root)
            for count, (el, attr, value) in enumerate(_value_nodes(root)):
                if count >= MAX_VALUE_NODES:
                    break
                selector = f"{prefix} {_relative_selector(root, el, common_classes, index_of_root)}".strip()
                key = (selector, attr)
                draft = drafts.get(key)
                if draft is None:
                    spec = f"{selector}@{attr}" if attr else selector
                    draft = drafts[key] = _FieldDraft(selectors=[spec], values={}, position=position,
                                                      attr=attr, tag=el.name)
                if attr is None and index not in draft.values:
                    for kind, word in _element_hints(el).items():
                        draft.hints.setdefault(kind, Counter())[word] += 1
                draft.values.setdefault(index, value)
                position += 1

    paired = [key for key in drafts if key[0].startswith("+")]
    if paired:
        own = {key for key in drafts if not key[0].startswith("+")}
        repeated = sum(1 for selector, attr in paired if (selector[1:].strip(), attr) in own)
        if repeated >= 0.5 * len(paired):
            # Two neighbouring cards are two records. A pair is a title row and its details row.
            for key in paired:
                del drafts[key]

    kept: List[_FieldDraft] = []
    for draft in sorted(drafts.values(), key=lambda d: d.position):
        if len(draft.values) < MIN_COVERAGE * len(sample):
            continue
        distinct = set(draft.values.values())
        if len(distinct) == 1 and len(sample) >= MIN_ITEMS and not _is_named_status(draft):
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
        _add_single_class_fallbacks(draft, sample)

    for draft in kept:
        if draft.attr == "href":
            draft.type = "url"
        elif draft.attr in ("src", "data-src"):
            draft.type = "image"
        elif draft.attr == "datetime":
            draft.type = "date"
        else:
            draft.type = infer_type(list(draft.values.values()))
    return kept[:DISCOVERED_FIELDS]


def _add_single_class_fallbacks(draft: _FieldDraft, sample: List[Tag]) -> None:
    """Extend the ladder of a multi-class selector with its single-class forms.

    ``p.instock.availability`` stops matching an item that is out of stock.
    ``p.availability`` still finds it, so it is added as a fallback, provided
    it picks the same element on every sampled item.
    """
    primary, _, attr = draft.selectors[0].partition("@")
    if primary.startswith("+"):
        return  # read from the element after the item; fallbacks are not derived for those
    head, _, last = primary.rpartition(" ")
    tokens = TOKEN_RE.findall(last)
    tag = TOKEN_RE.sub("", last)
    if len(tokens) < 2 or ":" in tag:
        return
    # A hook says what the element is, so it is the first fallback; then the last class,
    # which is usually the most specific name.
    for token in sorted(reversed(tokens), key=lambda t: not t.startswith("[")):
        variant = f"{head} {tag}{token}".strip()
        agrees = 0
        for item in sample:
            try:
                wanted = item.select_one(primary)
                if wanted is not None and _same_elements(item.select(variant), [wanted]):
                    agrees += 1
                elif wanted is not None:
                    agrees = -1
                    break
            except Exception:
                agrees = -1
                break
        spec = f"{variant}@{attr}" if attr else variant
        if agrees >= MIN_ITEMS and spec not in draft.selectors:
            draft.selectors.append(spec)


def _is_named_status(draft: _FieldDraft) -> bool:
    """True for a repeated value that is still data, such as "In stock" in ``p.availability``.

    Buttons, links and labels ("Add to basket", "Price:") repeat too, and are not data.
    """
    if draft.attr is not None or draft.tag in CONTROL_TAGS:
        return False
    value = next(iter(draft.values.values()))
    if value.endswith(":"):
        return False
    name = _class_based_name(draft.selectors[0])
    return name is not None and name not in GENERIC_CLASS_NAMES


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
    columns. Table cells are kept when the rows agree with each other, even if
    not every sampled row has them: the heading row of a plain table is one of
    the rows, and it has ``th`` cells where the others have ``td``.
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
        cells = all(TABLE_CELL_ONLY_RE.match(m.selectors[0].split("@")[0]) for m in members)
        if min(counts) < 0.9 * max(counts) or (max(counts) < sampled and not cells):
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
    hooks = [value for _, value in HOOK_RE.findall(last)]
    classes = [c for c in re.findall(r"\.([A-Za-z_][\w-]*)", HOOK_RE.sub("", last))
               if not _looks_generated(c) and not _is_layout_class(c)]
    if not hooks and not classes:
        return None
    # "list-title mathjax": the class that says what the value is beats the last one.
    # A hook (itemprop, data-testid) was written to say what the element is, so it comes first.
    fallback = hooks[0] if hooks else classes[-1]
    chosen = next((c for c in hooks + classes if any(word in c.lower() for word in FIELD_WORDS)), fallback)
    return _slug(re.sub(r"^(?:u|p|dt)-(?=[a-z])", "", chosen))  # "u-author" is microformat for "author"


def _slug(words: str) -> Optional[str]:
    """``programmingLanguage`` / ``card-headline`` / ``Stars today`` as a column name."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", words)
    name = re.sub(r"[^a-z0-9]+", "_", spaced.lower()).strip("_")
    return name if 2 <= len(name) <= 40 and not name.isdigit() else None


UNIT_RE = re.compile(r"^[\d.,]+\s?[kKmM]?\+?\s+([A-Za-z][A-Za-z ]{1,24})$")
LABEL_RE = re.compile(r"^([A-Za-z][A-Za-z ]{1,24}):\s+\S")
AGE_RE = re.compile(r"^(?:an?|\d+)\s+(?:second|minute|hour|day|week|month|year)s?\s+ago$", re.I)


def _hinted_name(f: _FieldDraft) -> Tuple[Optional[str], str]:
    """A name from what the page says around or in the values, and where it came from.

    Tried when the element has no class or hook of its own: the constant end of
    its link, an icon's label, the unit after a number ("9 comments"), a label
    before the value ("Language: Go"), or the look of the value ("3 hours ago").
    """
    filled = len(f.values)
    enough = max(MIN_ITEMS, 0.8 * filled)
    for kind in ("href", "icon", "aria"):
        seen = f.hints.get(kind)
        if seen:
            word, count = seen.most_common(1)[0]
            name = _slug(word)
            if count >= enough and name and re.search(r"[a-z]{2}", name) and len(name) <= 24:
                return name, kind
    values = list(f.values.values())
    if sum(1 for value in values if AGE_RE.match(value)) >= enough:
        return "age", "age"
    for pattern, kind in ((UNIT_RE, "unit"), (LABEL_RE, "label")):
        words = [m.group(1).strip().lower() for m in map(pattern.match, values) if m]
        # "1 comment" and "9 comments" are the same word.
        stems = Counter(re.sub(r"s\b", "", word) for word in words)
        if stems and stems.most_common(1)[0][1] >= enough:
            stem = stems.most_common(1)[0][0]
            plural = Counter(w for w in words if re.sub(r"s\b", "", w) == stem).most_common(1)[0][0]
            name = _slug(plural)
            if name:
                return name, kind
    return None, ""


BREAKPOINT_TOKENS = {"xs", "sm", "md", "lg", "xl", "xxl"}
UTILITY_TOKENS = {"btn", "col", "row", "flex", "float", "grid"}
UTILITY_HEADS = {
    "d", "f", "fw", "fs", "lh", "m", "mt", "mb", "ml", "mr", "mx", "my", "p", "pt", "pb", "pl", "pr", "px", "py",
    "w", "h", "v", "no", "text", "color", "bg", "border", "rounded", "align", "justify", "position", "overflow",
    "top", "right", "left", "bottom", "hide", "show", "tmp", "is", "has", "js",
}


def _is_layout_class(class_name: str) -> bool:
    """True for utility classes ("d-md-inline", "fw-medium", "float-sm-right"): styling, not meaning."""
    lowered = class_name.lower()
    if any(word in lowered for word in FIELD_WORDS):
        return False
    tokens = [t for t in re.split(r"[-_]+", lowered) if t]
    if not tokens:
        return True
    # A prefix only marks a utility when something follows it: "text-muted" yes, plain "text" no.
    prefixed = len(tokens) >= 2 and tokens[0] in UTILITY_HEADS
    return prefixed or bool(set(tokens) & (BREAKPOINT_TOKENS | UTILITY_TOKENS))


def _looks_generated(class_name: str) -> bool:
    """True for class names a build tool made up ("jeApUG", "ewmvhb"), which make poor field names."""
    if re.search(r"[-_]", class_name):
        return False
    if sum(1 for c in class_name[1:] if c.isupper()) >= 2:
        return True
    longest_run = max((len(run) for run in re.findall(r"[^aeiouy\d]+", class_name.lower())), default=0)
    vowels = sum(1 for c in class_name.lower() if c in VOWELS)
    return len(class_name) >= 5 and (longest_run >= 5 or vowels / len(class_name) < 0.2)


def _table_columns(row: Tag) -> Dict[str, str]:
    """For a table row, map each cell's selector step to its column heading.

    ``{"th": "location", "td:nth-of-type(1)": "population"}``. Empty if the row
    is not in a table, or the table has no simple one-row heading.
    """
    table = row.find_parent("table") if row.name == "tr" else None
    if table is None:
        return {}
    first = table.find("tr")
    if first is None or first is row:
        return {}
    headings = first.find_all(["th", "td"], recursive=False)
    cells = row.find_all(["th", "td"], recursive=False)
    spans = any(c.get("colspan") not in (None, "1") or c.get("rowspan") not in (None, "1") for c in headings + cells)
    if len(headings) < 2 or len(headings) != len(cells) or spans or not all(h.name == "th" for h in headings):
        return {}
    columns: Dict[str, str] = {}
    counts = Counter(c.name for c in cells)
    seen: Counter = Counter()
    for heading, cell in zip(headings, cells):
        seen[cell.name] += 1
        step = cell.name if counts[cell.name] == 1 else f"{cell.name}:nth-of-type({seen[cell.name]})"
        name = re.sub(r"[^a-z0-9]+", "_", clean_text(heading.get_text(" ", strip=True)).lower()).strip("_")[:40]
        if name:
            columns[step] = name
    return columns


def _cell_step(row: Tag, css: str) -> Optional[str]:
    """The selector step (``td:nth-of-type(2)``) of the cell in ``row`` holding what ``css`` selects."""
    try:
        el = row.select_one(css) if css else None
    except Exception:
        return None
    while isinstance(el, Tag) and el.parent is not row:
        el = el.parent
    if not isinstance(el, Tag) or el.name not in ("td", "th"):
        return None
    same = row.find_all(el.name, recursive=False)
    position = next(i for i, cell in enumerate(same, 1) if cell is el)
    return el.name if len(same) == 1 else f"{el.name}:nth-of-type({position})"


def _name_fields(fields: List[_FieldDraft], container: str = "", columns: Optional[Dict[str, str]] = None,
                 row: Optional[Tag] = None) -> None:
    """Give every field a column name. ``columns`` and ``row`` come from a table with headings."""
    by_type = {"money": "price", "image": "image", "url": "url", "date": "date", "email": "email"}
    columns = columns or {}

    def column_name(f: _FieldDraft) -> Optional[str]:
        css = f.selectors[0].split("@")[0]
        cell = TABLE_CELL_RE.match(css)
        if cell:
            return columns.get(cell.group(1))
        if columns and row is not None and not css.startswith("+") and not _class_based_name(css):
            # Not the cell itself but something in it: the country name is a link inside the cell.
            # A value with a class of its own keeps that name ("wins" says more than "W").
            return columns.get(_cell_step(row, css) or "")
        return None

    def average_length(f: _FieldDraft) -> float:
        return sum(len(v) for v in f.values.values()) / max(len(f.values), 1)

    def title_strength(f: _FieldDraft) -> int:
        """2: a heading, a title attribute or a class that says "title". 1: link text. 0: not a title."""
        if f.type != "text" or average_length(f) < 3:
            return 0
        css = f.selectors[0].split("@")[0]
        # "list-title" on a plain div is the page saying which value is the title.
        says_title = {"title", "headline"} & set((_class_based_name(css) or "").split("_"))
        if f.attr == "title" or HEADING_RE.search(css) or says_title:
            return 2
        return 1 if re.search(r"(^|[\s>])a([.\s:\[]|$)", css) else 0

    strongest = max((title_strength(f) for f in fields if not column_name(f)), default=0)
    title_field = next((f for f in fields if strongest and not column_name(f)
                        and title_strength(f) == strongest), None)
    if columns:
        title_field = None  # a table already names its columns; none of them is "the title"

    # Fields with no class of their own may still share a named parent: "span.byline > a".
    def parent_name(f: _FieldDraft) -> Optional[str]:
        head, arrow, last = f.selectors[0].split("@")[0].rpartition(" > ")
        return _class_based_name(head) if arrow and not TOKEN_RE.search(last) else None

    parents = Counter(parent_name(f) for f in fields if f.type not in by_type)

    unnamed = set()
    link_noise = set()   # named after their own link's ending: that link adds nothing as a column
    for f in fields:
        selector = f.selectors[0]
        if column_name(f) and f.type not in ("url", "image"):
            f.name = column_name(f)  # the table's own heading beats any guess
            continue
        if f.type in by_type:
            f.name = by_type[f.type]
            continue
        if f is title_field:
            f.name = "title"
            continue
        from_class = _class_based_name(selector)
        if not from_class and f is not title_field:
            from_class, source = _hinted_name(f)
            if source == "href":
                link_noise.add(id(f))
            if not from_class and parents[parent_name(f)] == 1:
                from_class = parent_name(f)
        f.name = from_class or ("number" if f.type == "number" else "text")
        if not from_class:
            unnamed.add(id(f))
        # "country_capital" inside a ".country" block reads better as "capital".
        for prefix in re.findall(r"\.([A-Za-z_][\w-]*)", container):
            prefix = re.sub(r"[^a-z0-9]+", "_", prefix.lower()).strip("_") + "_"
            if f.name.startswith(prefix) and len(f.name) - len(prefix) >= 2:
                f.name = f.name[len(prefix):]
                break

    if title_field is None and not columns:
        # No heading or link text: call the longest field that has no name of its own the title.
        generic = [f for f in fields if id(f) in unnamed and f.type == "text"]
        if generic:
            chosen = max(generic, key=average_length)
            chosen.name = "title"
            unnamed.discard(id(chosen))
    elif title_field is not None and not any(f.name in ("description", "summary") for f in fields):
        # A sentence or more under a title, with no name of its own, is the description.
        long_text = [f for f in fields if id(f) in unnamed and f.type == "text" and average_length(f) >= 40
                     and f.selectors[0].lstrip("+ ")]  # not the item's whole text run together
        if long_text:
            chosen = max(long_text, key=average_length)
            chosen.name = "description"
            unnamed.discard(id(chosen))

    _drop_shared_prefix([f for f in fields if id(f) not in unnamed and f.type not in by_type and f.name != "title"])
    _name_links(fields, unnamed | link_noise)

    used: Counter = Counter()
    for f in fields:
        used[f.name] += 1
        if used[f.name] > 1:
            f.name = f"{f.name}_{used[f.name]}"
    # Title first, then readable values, with long links and image addresses last.
    fields.sort(key=lambda f: (f.name != "title", f.type in ("url", "image"), f.position))
    del fields[MAX_FIELDS:]


def _drop_shared_prefix(named: List[_FieldDraft]) -> None:
    """``list_title, list_authors, list_subjects`` read better as ``title, authors, subjects``."""
    by_prefix: Dict[str, List[_FieldDraft]] = defaultdict(list)
    for f in named:
        head, sep, rest = f.name.partition("_")
        if sep and len(rest) >= 2:
            by_prefix[head].append(f)
    taken = {f.name for f in named}
    for prefix, group in by_prefix.items():
        shortened = [f.name[len(prefix) + 1:] for f in group]
        if len(group) >= 2 and len(set(shortened)) == len(shortened) and not (set(shortened) & (taken - {f.name for f in group})):
            for f, short in zip(group, shortened):
                f.name = short


def _name_links(fields: List[_FieldDraft], generic: Optional[set] = None) -> None:
    """Name each link after the text it belongs to, and drop links and images nobody would miss.

    A card often has a link on its title, another on the author and one on the
    comment count, plus icons. ``url``, ``author_url`` and ``comments_url`` say
    which is which; ``url_2`` to ``url_6`` do not. A link with no text of its
    own (an icon) is kept only when the record has no other link. One image is kept.
    """
    def css_of(spec: str) -> str:
        return spec.rpartition("@")[0] if "@" in spec else spec

    text_by_css: Dict[str, _FieldDraft] = {}
    for f in fields:
        if f.type not in ("url", "image"):
            for spec in f.selectors:
                text_by_css.setdefault(css_of(spec), f)

    kept: List[_FieldDraft] = []
    spare_links: List[_FieldDraft] = []
    has_main_link = False
    has_image = False
    for f in fields:
        if f.type == "image":
            if not has_image:
                has_image = True
                kept.append(f)
            continue
        if f.type != "url":
            kept.append(f)
            continue
        owner = next((text_by_css[css_of(s)] for s in f.selectors if css_of(s) in text_by_css), None)
        if owner is None or (generic and id(owner) in generic and owner.name != "title"):
            spare_links.append(f)  # "text_url" would say nothing about what the link is
        elif owner.name == "title" and not has_main_link:
            f.name, has_main_link = "url", True
            kept.append(f)
        else:
            f.name = f"{owner.name}_url"
            kept.append(f)
    if not has_main_link and spare_links:
        spare_links[0].name = "url"
        kept.append(spare_links[0])
    fields[:] = kept


def _in_page_chrome(item: Tag) -> bool:
    """True if the block sits in page furniture: navigation, header, footer, sidebar.

    Furniture tags always count. A furniture *word* in a class or id counts
    unless the block is inside the page's main content landmark: sites do mark
    up a list of posts as ``<ul class="menu">`` inside ``<section role="main">``.
    """
    named_as_furniture = False
    node: Optional[Tag] = item
    while isinstance(node, Tag):
        if node.name in CHROME_TAGS:
            return True
        if node.name == "main" or node.get("role") == "main":
            return False
        tokens = set()
        for word in _classes(node) + [node.get("id") or "", node.get("role") or ""]:
            tokens.update(re.split(r"[-_\s]+", str(word).lower()))
        if tokens & CHROME_WORDS or any(CHROME_TOKEN_RE.match(t) for t in tokens if t):
            named_as_furniture = True
        node = node.parent
    return named_as_furniture


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
    links = len(fields) - len(readable)
    # A value reachable by a class or tag is a column. One reachable only by counting
    # ("the 7th div") usually means the block is a mixed section, not a record.
    named = sum(0.5 if ":nth-of-type(" in f.selectors[0] and not TABLE_CELL_RE.match(f.selectors[0]) else 1.0
                for f in readable)
    breadth = min(named, 8) + 0.5 * min(links, 2)
    if all(f.tag == "a" for f in readable):
        # Nothing but link text. Seven links in a menu are not seven columns.
        breadth = min(breadth, 1.5)
    score = (breadth + 2 * richness) * coverage * math.log2(len(items) + 1)
    if len(items) <= 4:
        # Three or four big blocks are usually sections of a page. They still win
        # when nothing larger competes, so a genuine list of four is not lost.
        score *= 0.6
    return score * (0.3 if _in_page_chrome(items[0]) else 1.0)


def _is_wrapper(outer: _Candidate, inner: _Candidate) -> bool:
    """True if each outer item holds several inner items (a row of cards, not a card)."""
    if len(inner.items) < 2 * len(outer.items):
        return False
    # The inner block must itself look like a record (two or more readable values).
    # A blog entry holding a title link and an author link is not "a wrapper of links".
    if sum(1 for f in inner.fields if f.type not in ("url", "image")) < 2:
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


def _same_records(outer: _Candidate, inner: _Candidate) -> bool:
    """True if each inner item lies inside the outer block's record at the same position."""
    if len(outer.items) != len(inner.items):
        return False
    for index, inner_item in enumerate(inner.items):
        roots = [outer.items[index]]
        if outer.partners and outer.partners[index] is not None:
            roots.append(outer.partners[index])
        if not any(root is not inner_item and root in inner_item.parents for root in roots):
            return False
    return True


def _share_covered(holder: _Candidate, other: _Candidate) -> float:
    """Share of ``other``'s fields whose values ``holder`` also has."""
    if not other.fields:
        return 1.0
    return sum(1 for f in other.fields if any(h.values == f.values for h in holder.fields)) / len(other.fields)


def _settle_extent(chosen: _Candidate, candidates: List[_Candidate]) -> _Candidate:
    """Choose between nested blocks that describe the same records, by what each one holds.

    Outward: a block that contains this one and adds fields is the fuller
    record. A repository card holds a "stars and forks" line; the card is the
    record, the line is not.

    Inward: a block inside this one that loses no field has the cleaner
    selector. ``li.col-xs-6 > article.product_pod``: same data, but the inner
    element is named for what it is.
    """
    def is_fuller(outer: _Candidate) -> bool:
        if not _same_records(outer, chosen):
            return False
        adds_fields = _share_covered(outer, chosen) >= 0.8 and _share_covered(chosen, outer) < 1.0
        # One element that encloses a pair and holds the same fields is the simpler recipe.
        replaces_pair = chosen.partners is not None and outer.partners is None \
            and _share_covered(outer, chosen) >= 1.0
        return adds_fields or replaces_pair

    for _ in range(10):  # nesting is never this deep; a bound keeps the loop obviously finite
        fuller = next((o for o in candidates if o is not chosen and is_fuller(o)), None)
        if fuller is not None:
            chosen = fuller
            continue
        cleaner = next(
            (o for o in candidates if o is not chosen and o.partners is None
             and _same_records(chosen, o) and _share_covered(o, chosen) >= 1.0),
            None,
        )
        if cleaner is None:
            break
        chosen = cleaner
    return chosen


def _widen(chosen: _Candidate, candidates: List[_Candidate]) -> _Candidate:
    """Prefer the block that holds these items and more of the same kind.

    A news page lays its cards out in several ways, each with its own marker.
    One layout scores best because its cards are the most alike, but the list a
    person wants is all the cards. A larger block qualifies when it contains
    every chosen item and reads nearly all the same fields the same way. Rows
    of another kind (a table's spacer rows) do not have those fields, so a
    block that merely surrounds the chosen one does not qualify.
    """
    mine = {id(item) for item in chosen.items}
    wanted = {f.selectors[0] for f in chosen.fields}
    best = chosen
    for other in candidates:
        if other is chosen or other.partners is not None or chosen.partners is not None:
            continue
        if len(other.items) <= len(best.items) or not mine < {id(item) for item in other.items}:
            continue
        shared = wanted & {f.selectors[0] for f in other.fields}
        if len(shared) >= 0.8 * len(wanted):
            best = other
    return best


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


MAX_FRAMES = 4


def content_frames(html: str, url: str) -> List[str]:
    """Addresses of the frames on this page that belong to the same site, in page order.

    Some pages are a shell: a menu, and a frame that holds the actual list. A
    frame from another host is an advert, a video or a widget, never the data.
    A page with more frames than a handful is not a shell, and gives nothing.
    """
    host = urlparse(url).hostname
    found: List[str] = []
    for frame in parse(html).find_all(["iframe", "frame"]):
        src = (frame.get("src") or "").strip()
        if not src or src.startswith(("about:", "javascript:", "data:")):
            continue
        address = urljoin(url, src)
        if urlparse(address).hostname == host and address.split("#")[0] != url.split("#")[0]                 and address not in found:
            found.append(address)
    return found if len(found) <= MAX_FRAMES else []


def default_name(url: str) -> str:
    """A short file-friendly name from the URL's host: books.toscrape.com -> books."""
    host = (urlparse(url).hostname or "data").lower()
    labels = [label for label in host.split(".") if label and label != "www"]
    if not labels or all(label.isdigit() for label in labels):
        return "data"  # an IP address makes a poor file name
    name = labels[0]
    return re.sub(r"[^a-z0-9_-]+", "_", name).strip("_") or "data"


def page_pagination(soup: BeautifulSoup, url: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """The recipe's pagination rule for this page, and the next page's address if it has one."""
    detected = PaginationDetector(soup, url).detect()
    next_url = detected.get("next_url")
    if next_url and detected["type"] == "next_button" and detected.get("selector"):
        pagination: Dict[str, Any] = {"type": "next_link", "select": detected["selector"], "max_pages": 1}
    elif next_url:
        pagination = {"type": "auto", "max_pages": 1}
    elif detected["type"] == "load_more":
        # Clicked in a browser, so a text-based selector is fine when the button has no id or class.
        text = detected.get("text", "").replace('"', "")
        pagination = {
            "type": "load_more",
            "select": detected.get("selector") or f'{detected.get("tag", "button")}:has-text("{text}")',
            "max_pages": 1,
        }
    else:
        pagination = {"type": "none"}
    return pagination, next_url


def _to_recipe(candidate: _Candidate, soup: BeautifulSoup, url: str, name: Optional[str], fetch_mode: str):
    fields = [Field(name=f.name, select=f.selectors, type=f.type) for f in candidate.fields]
    pagination, next_url = page_pagination(soup, url)
    recipe = Recipe(
        name=name or default_name(url),
        url=url,
        container=candidate.selector,
        fields=fields,
        fetch=fetch_mode,
        pagination=pagination,
    )
    return recipe, next_url


def rank_candidates(soup: BeautifulSoup, likes: Optional[List[str]] = None) -> List[_Candidate]:
    """Every repeating block on the page that could be the data, best first, with named fields.

    With ``likes``, only blocks containing the most example values are returned;
    an empty list means none of the values is on the page.
    """
    likes = [like for like in (likes or []) if clean_text(like)]

    candidates: List[_Candidate] = []
    for selector, items in _candidate_selectors(soup):
        if len(candidates) >= MAX_CANDIDATES:
            break
        partners = _partners(items)
        fields = _discover_fields(items, partners)
        if not fields:
            continue
        if not any(f.selectors[0].startswith("+") for f in fields):
            partners = None  # nothing is read from the neighbour, so this is not a paired layout
        score = _score(items, fields)
        if score > 0:
            candidates.append(_Candidate(selector, items, fields, score, partners))
    if not candidates:
        return []

    if likes:
        hits = {id(c): sum(1 for like in likes if _matches(c.items, like)) for c in candidates}
        best = max(hits.values())
        if best == 0:
            return []  # nothing on the page contains the example values
        candidates = [c for c in candidates if hits[id(c)] == best]

    candidates.sort(key=lambda c: c.score, reverse=True)
    leaders = candidates[:8]
    ranked = [c for c in candidates if not any(_is_wrapper(c, other) for other in leaders if other is not c)]

    ordered = ranked or candidates
    # The leaders check is cheap but can miss a lower-scored block of real records.
    # Whatever ends up first is checked against every candidate.
    while len(ordered) > 1 and any(_is_wrapper(ordered[0], other) for other in candidates if other is not ordered[0]):
        ordered = ordered[1:]
    first = _settle_extent(_widen(ordered[0], candidates), candidates)
    ordered = [first] + [c for c in ordered if c is not first]
    for candidate in ordered:
        last_row = candidate.items[-1]
        _name_fields(candidate.fields, candidate.selector, _table_columns(last_row), last_row)
        if likes:
            wanted = [clean_text(like).lower() for like in likes]
            candidate.fields.sort(
                key=lambda f: not any(w in v.lower() for w in wanted for v in f.values.values())
            )
    return ordered


def candidate_recipe(candidate: _Candidate, soup: BeautifulSoup, url: str,
                     name: Optional[str] = None, fetch_mode: str = "http") -> Tuple[Recipe, Optional[str]]:
    """Turn one candidate block into a recipe. Returns (recipe, next page URL or None)."""
    return _to_recipe(candidate, soup, url, name, fetch_mode)


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

    def finished(recipe: Recipe, next_url: Optional[str], in_menu: bool = False) -> Optional[BuildResult]:
        # Accept the recipe only if it really works on the page it was built from.
        records = extract_records(soup, recipe, url)
        if len(records) < MIN_ITEMS:
            return None
        well_filled = [
            f.name for f in recipe.fields
            if f.type not in ("url", "image")
            and sum(1 for r in records if r.get(f.name) is not None) >= 0.95 * len(records)
        ]
        recipe.checks = {"min_records": max(1, len(records) // 2), "required": well_filled[:2]}
        return BuildResult(recipe=recipe, records=records, next_url=next_url, in_menu=in_menu)

    from_html: Optional[BuildResult] = None
    for candidate in rank_candidates(soup, likes):
        recipe, next_url = _to_recipe(candidate, soup, url, name, fetch_mode)
        from_html = finished(recipe, next_url, in_menu=_in_page_chrome(candidate.items[0]))
        if from_html:
            break
    if from_html and not from_html.in_menu:
        return from_html

    # Nothing in the HTML but perhaps a menu: a page drawn by JavaScript. The list it is
    # about to draw is often shipped as data in the same response.
    if fetch_mode == "http":
        pagination, next_url = page_pagination(soup, url)
        for container, fields in find_lists(soup, likes):
            recipe = Recipe(name=name or default_name(url), url=url, container=container, fields=fields,
                            fetch=fetch_mode, pagination=pagination)
            from_data = finished(recipe, next_url)
            if from_data:
                return from_data
    return from_html
