"""The everyday commands: get data from a page, and run a saved recipe again."""
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.table import Table

from scrapewizard.recipe.builder import BuildResult, build_recipe
from scrapewizard.recipe.detail import build_detail_fields
from scrapewizard.recipe.extract import RunResult, run_recipe
from scrapewizard.recipe.extract import parse
from scrapewizard.recipe.fetch import BrowserSession, FetchError, fetch, fetch_http
from scrapewizard.recipe.heal import RepairRefused, repair, what_broke
from scrapewizard.recipe.model import Recipe, RecipeError, load_recipe, save_recipe
from scrapewizard.recipe.output import FORMATS, OutputError, save_records
from scrapewizard.recipe.state import compare, load_state, save_state

console = Console()

PREVIEW_ROWS = 5
CELL_WIDTH = 26
ALL_PAGES = 1000  # safety cap for "all pages"


def _fail(message: str, hint: Optional[str] = None) -> "typer.Exit":
    """Print a plain error with an optional next step, and return the exit to raise."""
    console.print(f"[red]{message}[/red]")
    if hint:
        console.print(hint)
    return typer.Exit(code=1)


def _normalise_url(url: str) -> str:
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise _fail(f"'{url}' is not a web address.", "Example: scrapewizard https://books.toscrape.com")
    return url


def _show_preview(records: List[Dict[str, Any]]) -> None:
    """Show the first rows. Only as many columns as fit are shown; the rest are named."""
    columns = list(records[0].keys())
    fits = max(2, console.width // (CELL_WIDTH + 3))
    shown, hidden = columns[:fits], columns[fits:]

    table = Table(show_edge=False, header_style="bold")
    for column in shown:
        table.add_column(column, overflow="ellipsis", no_wrap=True,
                         min_width=min(CELL_WIDTH, max(len(column), 8)), max_width=CELL_WIDTH)
    for record in records[:PREVIEW_ROWS]:
        table.add_row(*("" if record.get(c) is None else str(record[c]) for c in shown))
    console.print(table)
    if len(records) > PREVIEW_ROWS:
        console.print(f"  ... {len(records) - PREVIEW_ROWS} more")
    if hidden:
        console.print(f"  (+{len(hidden)} more columns in the file: {', '.join(hidden)})")


def choose_pages(has_more: bool, read: Callable[[str], str] = input) -> Optional[int]:
    """Ask the one question. Returns pages to read, or None if the user quit."""
    options = "[Enter] this page   [a] all pages   [q] quit" if has_more else "[Enter] save   [q] quit"
    try:
        answer = read(f"Save?  {options}\n> ").strip().lower()
    except EOFError:
        answer = ""
    if answer in ("q", "quit", "n", "no"):
        return None
    if has_more and answer in ("a", "all"):
        return ALL_PAGES
    if has_more and answer.isdigit() and int(answer) > 0:
        return int(answer)
    return 1


def _build(url: str, likes: List[str], name: Optional[str], force_browser: bool) -> BuildResult:
    """Fetch the page the cheapest way that works and build a recipe from it."""
    host = urlparse(url).hostname
    console.print(f"Looking at {host} ...")
    http_error: Optional[FetchError] = None

    if not force_browser:
        try:
            result = build_recipe(fetch_http(url), url, likes=likes, name=name, fetch_mode="http")
            if result:
                console.print(f"Found {len(result.records)} items. No browser needed.")
                return result
        except FetchError as e:
            if not e.browser_may_help:
                raise _fail(str(e), "Check the address and your connection, then try again.")
            http_error = e
        if http_error:
            console.print(f"{http_error} Trying a browser ...")
        elif likes:
            console.print("Those values aren't in the plain page. Loading it in a browser ...")
        else:
            console.print("The plain page didn't show a list. Loading it in a browser ...")

    try:
        with BrowserSession() as session:
            result = build_recipe(session.open(url), url, likes=likes, name=name, fetch_mode="browser")
            if result and not result.has_more:
                _detect_scrolling(session, result)
    except FetchError as e:
        # If plain HTTP was refused too, that message says more about the cause.
        raise _fail(str(http_error or e))
    if result:
        console.print(f"Found {len(result.records)} items (the page needed a browser to load).")
        return result

    if likes:
        raise _fail("Couldn't find a list containing those example values.",
                    "Check the values are visible on the page, exactly as typed.")
    raise _fail("Couldn't find a repeating list on this page.",
                'Try:  scrapewizard <url> --like "a value you can see on the page"')


def _detect_scrolling(session: BrowserSession, result: BuildResult) -> None:
    """Scroll once: if more items appear, the list is an infinite scroll."""
    grown = session.scroll_more()
    if grown is None:
        return
    try:
        now = len(parse(grown).select(result.recipe.container))
    except Exception:
        return
    if now > len(result.records):
        result.recipe.pagination = {"type": "scroll", "max_pages": 1}


def _look_for_more_in_browser(url: str, likes: List[str], result: BuildResult) -> BuildResult:
    """More pages were asked for but the plain page shows no way to continue.

    Some lists only reveal their "next" control, or load more on scrolling,
    once scripts have run. Look again in a browser before settling for one page.
    """
    console.print("The plain page shows no next page. Checking in a browser whether it loads more ...")
    try:
        with BrowserSession() as session:
            rendered = build_recipe(session.open(url), url, likes=likes, name=result.recipe.name,
                                    fetch_mode="browser")
            if rendered and not rendered.has_more:
                _detect_scrolling(session, rendered)
    except FetchError as e:
        console.print(f"{e} Keeping the one page already read.")
        return result
    if rendered and rendered.has_more:
        return rendered
    console.print("It doesn't: this is the whole list.")
    return result


def _save(records: List[Dict[str, Any]], recipe: Optional[Recipe], name: str, fmt: str) -> Optional[Path]:
    """Save the data and, if given, the recipe. Returns the recipe's path."""
    data_path = Path(f"{name}.{fmt}")
    try:
        save_records(records, data_path, fmt)
    except OutputError as e:
        raise _fail(str(e))
    columns = len(records[0]) if records else 0
    console.print(f"[green]Saved[/green]  {data_path}   {len(records)} rows, {columns} columns", soft_wrap=True)
    if recipe is not None:
        recipe_path = save_recipe(recipe, Path(f"{name}.recipe.yaml"))
        # soft_wrap keeps the command on one line so it can be copied.
        console.print(f"       {recipe_path}   run again with: scrapewizard run {recipe_path}", soft_wrap=True)
        return recipe_path
    return None


def _output_name(out: Optional[str], fallback: str) -> str:
    """The file name without extension: --out wins, and a typed extension is dropped."""
    if not out:
        return fallback
    path = Path(out)
    return str(path.with_suffix("")) if path.suffix.lstrip(".") in FORMATS else out


def _run_pages(recipe: Recipe, pages: Optional[int]) -> RunResult:
    """Run a recipe, printing progress. ``pages`` of None means what the recipe says."""
    limit = pages if pages is not None else int(recipe.pagination.get("max_pages") or 1)

    def page_progress(done: int, rows: int) -> None:
        console.print(f"  page {done}: {rows} rows so far")

    def item_progress(done: int, total: int) -> None:
        if done % 10 == 0 or done == total:
            console.print(f"  item pages: {done} of {total}")

    return run_recipe(recipe, max_pages=pages, on_page=page_progress if limit > 1 else None,
                      on_item=item_progress)


ITEM_PAGES_SAMPLED = 3


def _add_item_pages(recipe: Recipe, records: List[Dict[str, Any]]) -> None:
    """Look at a few item pages and add the fields they hold to the recipe."""
    link = None
    for f in recipe.fields:
        values = [str(r[f.name]) for r in records if r.get(f.name)]
        if f.type == "url" and values and len(set(values)) >= 0.9 * len(records):
            link = f.name
            break
    if link is None:
        console.print("The items have no link of their own to follow. Continuing with the list only.")
        return

    sample = [r for r in records if r.get(link)][:ITEM_PAGES_SAMPLED]
    console.print(f"Opening {len(sample)} item pages to see what they hold ...")
    pages = []
    try:
        with BrowserSession() if recipe.fetch == "browser" else _NoSession() as session:
            for record in sample:
                address = str(record[link])
                pages.append(parse(session.open(address) if session else fetch_http(address)))
    except FetchError as e:
        console.print(f"{e} Continuing with the list only.")
        return

    fields = build_detail_fields(pages, sample, [f.name for f in recipe.fields])
    if not fields:
        console.print("The item pages hold nothing the list doesn't already have. Continuing with the list only.")
        return
    recipe.follow = link
    recipe.detail_fields = fields
    names = ", ".join(f.name for f in fields)
    console.print(f"Each item page adds {len(fields)} fields: {names}", soft_wrap=True)


class _NoSession:
    """Stands in for a browser session when item pages are read over plain HTTP."""

    def __enter__(self):
        return None

    def __exit__(self, *exc) -> None:
        return None


def get(
    url: str = typer.Argument(..., help="The page to get data from."),
    like: Optional[List[str]] = typer.Option(None, "--like", help="A value you can see on the page, to show which list you want. Repeatable."),
    fmt: str = typer.Option("csv", "--format", "-f", help="csv, json or xlsx."),
    pages: Optional[int] = typer.Option(None, "--pages", help="How many pages to read."),
    all_pages: bool = typer.Option(False, "--all-pages", help="Follow the list to its last page."),
    out: Optional[str] = typer.Option(None, "--out", "-o", help="File name to save as (without extension)."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask; save with the defaults."),
    follow: bool = typer.Option(False, "--follow", help="Also open each item's own page and collect what it holds."),
    browser: bool = typer.Option(False, "--browser", help="Load the page in a browser even if plain HTTP works."),
) -> None:
    """Look at a page, preview the data on it, and save it with a recipe.

    No AI key is needed. Shorthand: scrapewizard <url>
    """
    if fmt not in FORMATS:
        raise _fail(f"Unknown format '{fmt}'.", f"Use one of: {', '.join(FORMATS)}")
    url = _normalise_url(url)
    result = _build(url, list(like or []), None, browser)
    recipe = result.recipe

    console.print()
    _show_preview(result.records)
    console.print()
    if follow:
        _add_item_pages(recipe, result.records)
        console.print()

    has_more = result.has_more
    in_place = recipe.pagination.get("type") in ("load_more", "scroll")
    if has_more:
        console.print("This list loads more as you go." if in_place else "This list continues on more pages.")

    if all_pages:
        wanted = ALL_PAGES
    elif pages is not None:
        wanted = max(1, pages)
    elif yes or not sys.stdin.isatty():
        wanted = 1
    else:
        wanted = choose_pages(has_more)
        if wanted is None:
            console.print("Nothing saved.")
            raise typer.Exit(code=0)

    if wanted > 1 and not has_more and recipe.fetch == "http":
        result = _look_for_more_in_browser(url, list(like or []), result)
        recipe = result.recipe
        has_more = result.has_more
        in_place = recipe.pagination.get("type") in ("load_more", "scroll")

    records = result.records
    more_pages = wanted > 1 and has_more
    if more_pages or recipe.follow:
        if more_pages and in_place and recipe.fetch != "browser":
            console.print("Following it needs a browser. Starting one ...")
            recipe.fetch = "browser"
        try:
            records = _run_pages(recipe, wanted if more_pages else 1).records
        except FetchError as e:
            raise _fail(str(e))
        if more_pages:
            recipe.pagination["max_pages"] = wanted
            recipe.checks["min_records"] = max(1, len(records) // 2)

    console.print()
    name = _output_name(out, recipe.name)
    recipe.name = Path(name).name  # the recipe carries the name its files were saved under
    recipe_path = _save(records, recipe, name, fmt)
    save_state(recipe_path, recipe, records, wanted if has_more else 1)


def _recipe_stem(recipe_path: str) -> str:
    """shop.recipe.yaml -> shop: running a recipe saves data beside it under the same name."""
    name = Path(recipe_path).name
    for ending in (".recipe.yaml", ".recipe.yml", ".yaml", ".yml"):
        if name.endswith(ending):
            return name[: -len(ending)]
    return Path(name).stem


def run(
    recipe_path: str = typer.Argument(..., help="A .recipe.yaml file saved earlier."),
    fmt: str = typer.Option("csv", "--format", "-f", help="csv, json or xlsx."),
    pages: Optional[int] = typer.Option(None, "--pages", help="Pages to read (default: what the recipe says)."),
    all_pages: bool = typer.Option(False, "--all-pages", help="Follow the list to its last page."),
    out: Optional[str] = typer.Option(None, "--out", "-o", help="File name to save as (without extension)."),
    no_repair: bool = typer.Option(False, "--no-repair", help="Don't try to repair the recipe if the site changed."),
) -> None:
    """Run a saved recipe again. Exits with an error if its checks fail.

    If the site changed and the recipe stops matching, it is repaired and the
    repair is checked against the data from the last run.
    """
    if fmt not in FORMATS:
        raise _fail(f"Unknown format '{fmt}'.", f"Use one of: {', '.join(FORMATS)}")
    try:
        recipe = load_recipe(recipe_path)
    except RecipeError as e:
        raise _fail(str(e))

    state = load_state(recipe_path)
    limit = ALL_PAGES if all_pages else pages
    page_limit = limit or int(recipe.pagination.get("max_pages") or 1)

    def read() -> RunResult:
        try:
            return _run_pages(recipe, limit)
        except (FetchError, RecipeError) as e:
            raise _fail(str(e))

    result = read()
    problem = what_broke(result.records, recipe, state)
    if problem and not no_repair:
        console.print(problem)
        try:
            fix = repair(recipe, fetch(recipe.url, recipe.fetch), recipe.url, state)
        except FetchError as e:
            raise _fail(str(e))
        except RepairRefused as e:
            raise _fail(f"It could not be repaired safely: {e}.",
                        f"Nothing was saved. Build a fresh recipe with: scrapewizard {recipe.url}")
        for change in fix.changes:
            console.print(f"Repaired: {change}", soft_wrap=True)
        if fix.verified:
            console.print(f"Checked:  {len(fix.records)} rows on the first page, "
                          f"{fix.matched} of them known from the last run.")
        else:
            console.print("Checked:  the fields match by name and type. "
                          "No remembered items were on the page to compare with.")
        recipe = fix.recipe
        save_recipe(recipe, recipe_path)
        console.print("Recipe updated.")
        result = read()
        problem = what_broke(result.records, recipe, state)

    page_word = "page" if result.pages == 1 else "pages"
    changes = compare(state, result.records, page_limit)
    summary = f"{recipe.name}   {len(result.records)} rows from {result.pages} {page_word}"
    console.print(f"{summary}   {changes}" if changes else summary, soft_wrap=True)
    if not result.records:
        raise _fail("No records were found, so nothing was saved.",
                    "The site may have changed. Build a fresh recipe with: scrapewizard " + recipe.url)

    _save(result.records, None, _output_name(out, _recipe_stem(recipe_path)), fmt)
    if result.failures or problem:
        for failure in result.failures or [problem]:
            console.print(f"[red]Check failed:[/red] {failure}")
        raise typer.Exit(code=1)
    # Only a run that passed its checks becomes the memory the next run is compared with.
    save_state(recipe_path, recipe, result.records, page_limit)
    console.print("       all checks passed")
