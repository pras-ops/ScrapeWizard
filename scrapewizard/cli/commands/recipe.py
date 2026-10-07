"""The everyday commands: get data from a page, and run a saved recipe again."""
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.table import Table

from scrapewizard.recipe.builder import BuildResult, build_recipe
from scrapewizard.recipe.extract import RunResult, run_recipe
from scrapewizard.recipe.fetch import FetchError, fetch_browser, fetch_http
from scrapewizard.recipe.model import Recipe, RecipeError, load_recipe, save_recipe
from scrapewizard.recipe.output import FORMATS, OutputError, save_records

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
        result = build_recipe(fetch_browser(url), url, likes=likes, name=name, fetch_mode="browser")
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


def _save(records: List[Dict[str, Any]], recipe: Optional[Recipe], name: str, fmt: str) -> None:
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


def _output_name(out: Optional[str], fallback: str) -> str:
    """The file name without extension: --out wins, and a typed extension is dropped."""
    if not out:
        return fallback
    path = Path(out)
    return str(path.with_suffix("")) if path.suffix.lstrip(".") in FORMATS else out


def _run_pages(recipe: Recipe, pages: int) -> RunResult:
    def progress(done: int, rows: int) -> None:
        console.print(f"  page {done}: {rows} rows so far")
    return run_recipe(recipe, max_pages=pages, on_page=progress if pages > 1 else None)


def get(
    url: str = typer.Argument(..., help="The page to get data from."),
    like: Optional[List[str]] = typer.Option(None, "--like", help="A value you can see on the page, to show which list you want. Repeatable."),
    fmt: str = typer.Option("csv", "--format", "-f", help="csv, json or xlsx."),
    pages: Optional[int] = typer.Option(None, "--pages", help="How many pages to read."),
    all_pages: bool = typer.Option(False, "--all-pages", help="Follow the list to its last page."),
    out: Optional[str] = typer.Option(None, "--out", "-o", help="File name to save as (without extension)."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask; save with the defaults."),
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
    has_more = result.next_url is not None
    if has_more:
        console.print("This list continues on more pages.")

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

    records = result.records
    if wanted > 1 and has_more:
        try:
            records = _run_pages(recipe, wanted).records
        except FetchError as e:
            raise _fail(str(e))
        recipe.pagination["max_pages"] = wanted
        recipe.checks["min_records"] = max(1, len(records) // 2)

    console.print()
    name = _output_name(out, recipe.name)
    recipe.name = Path(name).name  # the recipe carries the name its files were saved under
    _save(records, recipe, name, fmt)


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
) -> None:
    """Run a saved recipe again. Exits with an error if its checks fail."""
    if fmt not in FORMATS:
        raise _fail(f"Unknown format '{fmt}'.", f"Use one of: {', '.join(FORMATS)}")
    try:
        recipe = load_recipe(recipe_path)
    except RecipeError as e:
        raise _fail(str(e))

    limit = ALL_PAGES if all_pages else pages
    try:
        result = _run_pages(recipe, limit) if limit else run_recipe(recipe)
    except (FetchError, RecipeError) as e:
        raise _fail(str(e))

    page_word = "page" if result.pages == 1 else "pages"
    console.print(f"{recipe.name}   {len(result.records)} rows from {result.pages} {page_word}")
    if not result.records:
        raise _fail("No records were found, so nothing was saved.",
                    "The site may have changed. Build a fresh recipe with: scrapewizard " + recipe.url)

    _save(result.records, None, _output_name(out, _recipe_stem(recipe_path)), fmt)
    if result.failures:
        for failure in result.failures:
            console.print(f"[red]Check failed:[/red] {failure}")
        raise typer.Exit(code=1)
    console.print("       all checks passed")
