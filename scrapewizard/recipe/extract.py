"""The recipe runtime: fetch pages, read records, follow pagination, run checks."""
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from scrapewizard.recipe.fetch import fetch
from scrapewizard.recipe.model import Recipe, RecipeError
from scrapewizard.recipe.types import clean_text, convert
from scrapewizard.recon.pagination import find_next_url

ATTR_RE = re.compile(r"^[\w:-]+$")
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
    """Read one value from an item. Returns None if nothing matches."""
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


def extract_records(soup: BeautifulSoup, recipe: Recipe, base_url: str) -> List[Dict[str, Any]]:
    """Read every item on one page. Items with no values at all are skipped."""
    try:
        items = soup.select(recipe.container)
    except Exception as e:
        raise RecipeError(f"The container selector is not valid CSS: {recipe.container}") from e

    records = []
    for item in items:
        record = {}
        for f in recipe.fields:
            value = None
            for spec in f.select:  # the selector ladder: first one that yields a value wins
                value = read_value(item, spec)
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
    fetcher: Callable[[str, str], str] = fetch,
    delay: float = 0.3,
    on_page: Optional[Callable[[int, int], None]] = None,
) -> RunResult:
    """Run a recipe and return its records with any failed checks.

    Args:
        max_pages: Pages to read. Defaults to the recipe's ``pagination.max_pages`` (1 if unset).
        fetcher: ``(url, mode) -> html``. Replaceable for tests.
        delay: Seconds to wait between pages, to be polite to the site.
        on_page: Called with (pages read, records so far) after each page.
    """
    limit = max_pages if max_pages is not None else int(recipe.pagination.get("max_pages") or 1)
    records: List[Dict[str, Any]] = []
    seen_records = set()
    visited = set()
    url: Optional[str] = recipe.url
    pages = 0

    while url and pages < limit and url not in visited:
        visited.add(url)
        soup = parse(fetcher(url, recipe.fetch))
        page_records = extract_records(soup, recipe, url)
        for record in page_records:
            key = tuple((k, str(v)) for k, v in record.items())
            if key not in seen_records:
                seen_records.add(key)
                records.append(record)
        pages += 1
        if on_page:
            on_page(pages, len(records))
        if not page_records or pages >= limit:
            break
        url = next_page_url(soup, recipe, url)
        if url:
            time.sleep(delay)

    return RunResult(records=records, pages=pages, failures=evaluate_checks(records, recipe))
