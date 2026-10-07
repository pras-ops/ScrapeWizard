"""Lists published as data inside the page.

Many sites ship the list they are about to draw as JSON in a ``<script>``:
Next.js (``__NEXT_DATA__``), Nuxt, JSON-LD for search engines, or a plain
``window.__STATE__ = {...}``. When the visible page is drawn by JavaScript,
that data is still there in the plain response, already structured. Reading
it needs no browser and no selectors.

A recipe says so with a container that starts with ``data:`` followed by the
path to the list (``data:props.pageProps.products``). Its fields are paths
inside each entry (``name``, ``price.amount``, ``images.0.url``).
"""
import json
import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from scrapewizard.recipe.model import Field
from scrapewizard.recipe.types import clean_text, infer_type

DATA_PREFIX = "data:"
MIN_ITEMS = 3
SAMPLE_SIZE = 12
MAX_FIELDS = 12
MAX_TEXT_LENGTH = 500
MAX_SCRIPT_SIZE = 3_000_000
MAX_DEPTH = 12
MAX_LISTS = 400

ASSIGNMENT_RE = re.compile(r"=\s*(?=[\[{])")
OPAQUE_RE = re.compile(r"^(?:[0-9a-f]{16,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f-]{20,}|[A-Za-z0-9+/_-]{32,}={0,2})$")
IMAGE_FILE_RE = re.compile(r"\.(?:jpe?g|png|gif|webp|avif|svg)(?:[?#]|$)", re.I)
TITLE_KEYS = ("title", "name", "headline", "label")
LINK_KEYS = ("url", "href", "link", "permalink", "slug", "path")
IMAGE_KEYS = ("image", "img", "thumbnail", "thumb", "photo", "picture", "avatar", "cover", "logo")
# Keys that only wrap the real entry: {"node": {...}}, {"item": {...}}, {"attributes": {...}}.
WRAPPER_KEYS = {"node", "item", "attributes", "data", "fields", "props"}
GENERIC_LEAVES = {"name", "title", "label", "value", "text", "display"}


def embedded_data(soup: BeautifulSoup) -> List[Any]:
    """Every piece of JSON the page carries in its scripts, in page order."""
    found: List[Any] = []
    decoder = json.JSONDecoder()
    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if not text.strip() or len(text) > MAX_SCRIPT_SIZE:
            continue
        if "json" in (script.get("type") or "").lower():
            try:
                found.append(json.loads(text))
            except ValueError:
                pass  # sites do publish broken JSON; skip that block
            continue
        # window.__STATE__ = {...};  Only real JSON is read: a JavaScript object with
        # unquoted keys is code, and guessing at code is not worth being wrong.
        tried = 0
        for match in ASSIGNMENT_RE.finditer(text):
            tried += 1
            if tried > 20:
                break
            try:
                value, end = decoder.raw_decode(text, match.end())
            except ValueError:
                continue
            if isinstance(value, (dict, list)) and end - match.end() >= 200:
                found.append(value)
    return found


def dig(node: Any, path: str) -> Any:
    """Follow ``a.b.0.c`` through nested data: names for objects, numbers for lists."""
    for key in [part for part in path.split(".") if part]:
        if isinstance(node, list):
            if not key.isdigit() or int(key) >= len(node):
                return None
            node = node[int(key)]
        elif isinstance(node, dict):
            node = node.get(key)
        else:
            return None
    return node


def data_items(soup: BeautifulSoup, container: str) -> List[Dict[str, Any]]:
    """The entries of the list a ``data:`` container points at.

    The path is tried in each piece of embedded data; the first that holds a
    list of entries there wins.
    """
    path = container[len(DATA_PREFIX):].strip()
    for blob in embedded_data(soup):
        node = dig(blob, path)
        if isinstance(node, list):
            entries = [entry for entry in node if isinstance(entry, dict)]
            if entries:
                return entries
    return []


def read_data_value(entry: Dict[str, Any], path: str) -> Optional[str]:
    """One value of an entry as text. A list of plain values is joined with commas."""
    value = dig(entry, path)
    if isinstance(value, list) and value and all(isinstance(v, (str, int, float)) and not isinstance(v, bool) for v in value):
        value = ", ".join(str(v) for v in value)
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    return clean_text(str(value)) or None


# ---------------------------------------------------------------- finding the list

def _lists(node: Any, path: List[str], depth: int, out: List[Tuple[str, List[Dict[str, Any]]]]) -> None:
    if depth > MAX_DEPTH or len(out) >= MAX_LISTS:
        return
    if isinstance(node, list):
        entries = [entry for entry in node if isinstance(entry, dict)]
        if len(entries) >= MIN_ITEMS and len(entries) >= 0.8 * len(node):
            out.append((".".join(path), entries))
            children = list(enumerate(node[:3]))  # the entries are alike: three show what is inside
        else:
            children = list(enumerate(node[:50]))
        for position, child in children:
            if isinstance(child, (dict, list)):
                _lists(child, path + [str(position)], depth + 1, out)
    elif isinstance(node, dict):
        for key, child in node.items():
            if isinstance(key, str) and key and "." not in key and not key.isdigit() and isinstance(child, (dict, list)):
                _lists(child, path + [key], depth + 1, out)


def _leaves(entry: Any, path: List[str], depth: int, out: Dict[str, str]) -> None:
    """Flatten one entry to ``{path: text}``, two levels deep at most."""
    if isinstance(entry, dict):
        if depth > 2:
            return
        for key, child in entry.items():
            if isinstance(key, str) and key and "." not in key and not key.startswith(("_", "@", "$")):
                _leaves(child, path + [key], depth + 1, out)
    elif isinstance(entry, list):
        if entry and all(isinstance(v, (str, int, float)) and not isinstance(v, bool) for v in entry):
            out[".".join(path)] = ", ".join(str(v) for v in entry)
        elif entry and isinstance(entry[0], dict) and depth <= 2:
            _leaves(entry[0], path + ["0"], depth + 1, out)
    elif isinstance(entry, (str, int, float)) and not isinstance(entry, bool):
        text = clean_text(str(entry))
        if text:
            out[".".join(path)] = text


def _own_keys(path: str) -> List[str]:
    """The names in a path, without list positions and without keys that only wrap the entry."""
    keys = [key for key in path.split(".") if not key.isdigit()]
    while len(keys) > 1 and keys[0] in WRAPPER_KEYS:
        keys = keys[1:]
    return keys


def _column_name(path: str) -> str:
    keys = _own_keys(path)
    if len(keys) > 1 and keys[-1].lower() in GENERIC_LEAVES:
        keys = keys[:-1]  # author.name is the author
    words = "_".join(keys[-2:])
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", words)
    return re.sub(r"[^a-z0-9]+", "_", spaced.lower()).strip("_") or "value"


def _field_type(path: str, values: List[str], numeric: bool) -> str:
    key = path.rsplit(".", 1)[-1].lower()
    looks_like_address = sum(1 for v in values if v.startswith(("http://", "https://", "/"))) >= 0.8 * len(values)
    # "images.0.url": any part of the path may say it is a picture, and so may the file's ending.
    pictures = sum(1 for v in values if IMAGE_FILE_RE.search(v)) >= 0.8 * len(values)
    if looks_like_address and (pictures or any(word in part for part in path.lower().split(".") for word in IMAGE_KEYS)):
        return "image"
    if looks_like_address and (any(word in key for word in LINK_KEYS) or values[0].startswith("http")):
        guessed = infer_type(values)
        return guessed if guessed in ("url", "image") else "url"
    if numeric:
        return "number"
    return infer_type(values)


def _describe(entries: List[Dict[str, Any]]) -> Optional[Tuple[List[Field], float]]:
    """The columns of a list of entries and how good a list it is, or None if it is not one."""
    sample = entries[:SAMPLE_SIZE]
    flat = []
    for entry in sample:
        leaves: Dict[str, str] = {}
        _leaves(entry, [], 0, leaves)
        flat.append(leaves)
    order: List[str] = []
    for leaves in flat:
        order.extend(path for path in leaves if path not in order)

    columns: List[Tuple[str, List[str], str]] = []
    for path in order:
        values = [leaves[path] for leaves in flat if path in leaves]
        if len(values) < 0.5 * len(sample) or len(set(values)) == 1:
            continue  # rarely there, or the same on every entry
        if sum(len(v) for v in values) / len(values) > MAX_TEXT_LENGTH:
            continue  # a whole article body, not a column
        if sum(1 for v in values if OPAQUE_RE.match(v)) >= 0.8 * len(values):
            continue  # hashes and tokens
        raw = [dig(entry, path) for entry in sample]
        numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in raw if v is not None)
        columns.append((path, values, _field_type(path, values, numeric)))

    texts = [c for c in columns if c[2] == "text"]
    # A list worth saving has something that reads like a name: text, mostly different on each entry.
    named = [c for c in texts if len(set(c[1])) >= 0.8 * len(c[1]) and sum(len(v) for v in c[1]) / len(c[1]) >= 5]
    if len(columns) < 3 or not named:
        return None

    # The entry's own name comes first. "author.name" is the author's name, not the entry's.
    title = next((c for c in named if len(_own_keys(c[0])) == 1 and _own_keys(c[0])[0].lower() in TITLE_KEYS), None)
    lead = title or max(named, key=lambda c: (len(_own_keys(c[0])) == 1, min(sum(len(v) for v in c[1]) / len(c[1]), 80)))
    ordered = [lead] + [c for c in columns if c is not lead]
    # Readable values first; addresses last. Then no more columns than a table can show.
    ordered.sort(key=lambda c: (c is not lead, c[2] in ("url", "image")))
    ordered = ordered[:MAX_FIELDS]

    fields: List[Field] = []
    used: Counter = Counter()
    has_link = has_image = False
    for path, values, kind in ordered:
        name = "title" if title is not None and path == title[0] else _column_name(path)
        if kind == "url" and not has_link and len(_own_keys(path)) == 1:
            name, has_link = "url", True   # the entry's own address, not its author's
        elif kind == "image" and not has_image:
            name, has_image = "image", True
        used[name] += 1
        fields.append(Field(name=name if used[name] == 1 else f"{name}_{used[name]}", select=[path], type=kind))

    coverage = sum(len(c[1]) for c in ordered) / (len(ordered) * len(sample))
    chars = sum(len(v) for c in ordered if c[2] not in ("url", "image") for v in c[1]) / len(sample)
    score = (min(len(ordered), 8) + 2 * min(chars, 400) / 400) * coverage * math.log2(len(entries) + 1)
    return fields, score


def find_lists(soup: BeautifulSoup, likes: Optional[List[str]] = None) -> List[Tuple[str, List[Field]]]:
    """Lists found in the page's embedded data, best first, as (container, fields).

    With ``likes``, only lists whose entries contain the most example values.
    """
    wanted = [clean_text(like).lower() for like in (likes or []) if clean_text(like)]
    found: List[Tuple[float, int, str, List[Field]]] = []
    seen = set()
    for blob in embedded_data(soup):
        lists: List[Tuple[str, List[Dict[str, Any]]]] = []
        _lists(blob, [], 0, lists)
        for path, entries in lists:
            if path in seen:
                continue
            described = _describe(entries)
            if described is None:
                continue
            seen.add(path)
            fields, score = described
            hits = 0
            if wanted:
                text = json.dumps(entries, ensure_ascii=False).lower()
                hits = sum(1 for like in wanted if like in text)
            found.append((score, hits, DATA_PREFIX + path, fields))
    if wanted:
        best = max((hits for _, hits, _, _ in found), default=0)
        found = [entry for entry in found if entry[1] == best and best > 0]
    found.sort(key=lambda entry: entry[0], reverse=True)
    return [(container, fields) for _, _, container, fields in found]
