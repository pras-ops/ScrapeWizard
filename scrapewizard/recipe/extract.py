"""The recipe runtime: fetch pages, read records, follow pagination, run checks."""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from scrapewizard.core.logging import log
from scrapewizard.recipe.fetch import BrowserSession, FetchError, fetch
from scrapewizard.recipe.embedded import DATA_PREFIX, data_items, read_data_value
from scrapewizard.recipe.model import IN_PLACE_PAGINATION, Field, Recipe, RecipeError
from scrapewizard.recipe.types import clean_text, convert
from scrapewizard.recon.pagination import find_next_url

ATTR_RE = re.compile(r"^[\w:-]+$")
# Item pages read at the same time over HTTP. Browsers open about this many
# connections to one site, so it is not an unusual load.
ITEM_PAGE_WORKERS = 4
# A required field may be empty in a few records before the check fails.
DEFAULT_REQUIRED_COVERAGE = 0.9


@dataclass
class RunResult:
    records: List[Dict[str, Any]]
    pages: int
    failures: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def split_selector(spec: str) -> Tuple[str, Optional[str]]:
    """Split 'css@attr' into (css, attr). A spec without '@attr' reads text."""
    css, sep, attr = spec.rpartition("@")
    if sep and ATTR_RE.match(attr):
        return css.strip(), attr
    return spec.strip(), None


def read_value(item: Tag, spec: str) -> Optional[str]:
    """Read one value from an item. Returns None if nothing matches.

    A spec starting with ``+`` reads from the element right after the item,
    for layouts that split one record over two neighbours (``dt`` + ``dd``,
    or a title row followed by a details row).
    """
    if spec.startswith("+"):
        item = item.find_next_sibling()
        if item is None:
            return None
        spec = spec[1:].strip()
    css, attr = split_selector(spec)
    try:
        target = item if not css else item.select_one(css)
    except Exception:
        return None  # a selector that is not valid CSS simply doesn't match
    if target is None:
        return None
    if attr:
        raw = target.get(attr)
        raw = " ".join(raw) if isinstance(raw, list) else raw
    else:
        raw = target.get_text(" ", strip=True)
    return clean_text(raw) or None


def jsonld_objects(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Every object in the page's JSON-LD blocks, including those inside ``@graph``."""
    found: List[Dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except ValueError:
            continue  # sites do publish broken JSON-LD; skip that block
        pending = [data]
        while pending:
            node = pending.pop(0)
            if isinstance(node, list):
                pending[0:0] = node
            elif isinstance(node, dict):
                found.append(node)
                if isinstance(node.get("@graph"), list):
                    pending.extend(node["@graph"])
    return found


def _dig(node: Any, path: str) -> Any:
    """Follow a dotted path through nested JSON. A list is entered at its first element."""
    for key in path.split("."):
        if isinstance(node, list):
            node = node[0] if node else None
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    if isinstance(node, list):
        node = node[0] if node else None
    return node if isinstance(node, (str, int, float)) and not isinstance(node, bool) else None


def read_document_value(soup: BeautifulSoup, spec: str,
                        structured: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
    """Read one value from a whole page.

    ``spec`` is CSS (optionally ``@attr``), ``jsonld:path.to.key`` for embedded
    structured data, or ``meta:name`` for a meta tag's content.
    """
    if spec.startswith("jsonld:"):
        for node in structured if structured is not None else jsonld_objects(soup):
            value = _dig(node, spec[len("jsonld:"):])
            if value is not None and clean_text(value):
                return clean_text(value)
        return None
    if spec.startswith("meta:"):
        name = spec[len("meta:"):]
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        return clean_text(tag.get("content")) or None if tag is not None else None
    return read_value(soup, spec)


def extract_detail(soup: BeautifulSoup, fields: List[Field], base_url: str) -> Dict[str, Any]:
    """Read an item page's fields."""
    structured = jsonld_objects(soup)
    record = {}
    for f in fields:
        value = None
        for spec in f.select:
            value = read_document_value(soup, spec, structured)
            if value:
                break
        record[f.name] = convert(value, f.type, base_url)
    return record


def extract_records(soup: BeautifulSoup, recipe: Recipe, base_url: str) -> List[Dict[str, Any]]:
    """Read every item on one page. Items with no values at all are skipped.

    A container starting with ``data:`` reads the list from JSON embedded in
    the page instead of from its HTML; the fields are then paths, not selectors.
    """
    if recipe.container.startswith(DATA_PREFIX):
        items: List[Any] = data_items(soup, recipe.container)
        read = read_data_value
    else:
        try:
            items = soup.select(recipe.container)
        except Exception as e:
            raise RecipeError(f"The container selector is not valid CSS: {recipe.container}") from e
        read = read_value

    records = []
    for item in items:
        record = {}
        for f in recipe.fields:
            value = None
            for spec in f.select:  # the selector ladder: first one that yields a value wins
                value = read(item, spec)
                if value:
                    break
            record[f.name] = convert(value, f.type, base_url)
        if any(v is not None for v in record.values()):
            records.append(record)
    return records


def next_page_url(soup: BeautifulSoup, recipe: Recipe, url: str) -> Optional[str]:
    """Work out the next page from the recipe's pagination rule."""
    kind = recipe.pagination.get("type", "none")
    if kind == "none":
        return None
    selector = recipe.pagination.get("select")
    if kind == "next_link" and selector:
        try:
            link = soup.select_one(selector)
        except Exception:
            link = None
        href = (link.get("href") or "").strip() if link is not None else ""
        if href and not href.startswith("#"):
            target = urljoin(url, href)
            return None if target == url else target
        # The stored selector no longer matches: fall back to detection.
    return find_next_url(soup, url)


def evaluate_checks(records: List[Dict[str, Any]], recipe: Recipe) -> List[str]:
    """Return a plain sentence for each check that failed."""
    failures = []
    checks = recipe.checks
    total = len(records)

    min_records = checks.get("min_records")
    if min_records and total < int(min_records):
        failures.append(f"Expected at least {min_records} records, got {total}.")

    coverage_needed = float(checks.get("required_coverage", DEFAULT_REQUIRED_COVERAGE))
    for name in checks.get("required", []) or []:
        if total == 0:
            break
        filled = sum(1 for r in records if r.get(name) is not None)
        if filled / total < coverage_needed:
            failures.append(f"'{name}' is filled in only {filled} of {total} records.")
    return failures


def run_recipe(
    recipe: Recipe,
    max_pages: Optional[int] = None,
    fetcher: Optional[Callable[[str, str], str]] = None,
    delay: float = 0.3,
    on_page: Optional[Callable[[int, int], None]] = None,
    session_factory: Callable[[], Any] = BrowserSession,
    on_item: Optional[Callable[[int, int], None]] = None,
) -> RunResult:
    """Run a recipe and return its records with any failed checks.

    Recipes that need a browser (``fetch: browser``, or a list that grows in
    place) keep one browser open for the whole run.

    Args:
        max_pages: Pages to read. Defaults to the recipe's ``pagination.max_pages`` (1 if unset).
        fetcher: ``(url, mode) -> html``. When given it is used for every page
            and no browser is opened; meant for tests.
        delay: Seconds to wait between pages, to be polite to the site.
        on_page: Called with (pages read, records so far) after each page.
        session_factory: Creates the browser session. Replaceable for tests.
        on_item: Called with (item pages read, total) while following items.
    """
    limit = max_pages if max_pages is not None else int(recipe.pagination.get("max_pages") or 1)
    in_place = recipe.pagination.get("type") in IN_PLACE_PAGINATION
    if fetcher is None and (recipe.fetch == "browser" or in_place):
        with session_factory() as session:
            return _read_pages(recipe, limit, session.open, session, delay, on_page, on_item)
    fetch_page = fetcher or fetch
    return _read_pages(recipe, limit, lambda url: fetch_page(url, recipe.fetch), None, delay, on_page, on_item)


def _follow_items(
    records: List[Dict[str, Any]],
    recipe: Recipe,
    open_url: Callable[[str], str],
    delay: float,
    on_item: Optional[Callable[[int, int], None]],
    parallel: bool,
) -> None:
    """Open each item's own page and add its fields to the record.

    Over plain HTTP a few pages are read at a time. In a browser there is one
    page, so they are read one after another.
    """
    targets = [r for r in records if r.get(recipe.follow)]

    def read(record: Dict[str, Any]) -> Dict[str, Any]:
        address = str(record[recipe.follow])
        try:
            return extract_detail(parse(open_url(address)), recipe.detail_fields, address)
        except FetchError as e:
            # One unreachable item page should not lose the whole run; its fields stay empty.
            log(f"Item page could not be read: {address} ({e})", level="warning")
            return {}

    if parallel and len(targets) > 1:
        with ThreadPoolExecutor(max_workers=ITEM_PAGE_WORKERS) as pool:
            pending = {pool.submit(read, record): record for record in targets}
            for done, future in enumerate(as_completed(pending), 1):
                pending[future].update(future.result())
                if on_item:
                    on_item(done, len(targets))
    else:
        for index, record in enumerate(targets, 1):
            record.update(read(record))
            if on_item:
                on_item(index, len(targets))
            if index < len(targets):
                time.sleep(delay)

    for record in records:
        for f in recipe.detail_fields:
            record.setdefault(f.name, None)


def _read_pages(
    recipe: Recipe,
    limit: int,
    open_url: Callable[[str], str],
    session: Optional[Any],
    delay: float,
    on_page: Optional[Callable[[int, int], None]],
    on_item: Optional[Callable[[int, int], None]] = None,
) -> RunResult:
    records: List[Dict[str, Any]] = []
    seen_records = set()
    kind = recipe.pagination.get("type", "none")
    url = recipe.url
    visited = {url}
    html = open_url(url)
    pages = 0
    stale_pages = 0  # consecutive pages that added nothing new

    while True:
        soup = parse(html)
        page_records = extract_records(soup, recipe, url)
        before = len(records)
        for record in page_records:
            key = tuple((k, str(v)) for k, v in record.items())
            if key not in seen_records:
                seen_records.add(key)
                records.append(record)
        pages += 1
        if on_page:
            on_page(pages, len(records))
        # One repeat is tolerated (some sites link page 1 to itself); two in a row is a loop.
        stale_pages = stale_pages + 1 if len(records) == before else 0
        if not page_records or stale_pages >= 2 or pages >= limit:
            break

        if kind in IN_PLACE_PAGINATION and session is not None:
            # The page itself grows: every read returns all items so far, and duplicates are skipped.
            grown = session.click_more(recipe.pagination.get("select") or "") if kind == "load_more" \
                else session.scroll_more()
            if grown is None:
                break
            html = grown
            continue

        next_url = next_page_url(soup, recipe, url)
        if not next_url or next_url in visited:
            break
        time.sleep(delay)
        url = next_url
        visited.add(url)
        html = open_url(url)

    if recipe.follow and recipe.detail_fields:
        _follow_items(records, recipe, open_url, min(delay, 0.2), on_item, parallel=session is None)

    return RunResult(records=records, pages=pages, failures=evaluate_checks(records, recipe))
