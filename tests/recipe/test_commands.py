"""The get and run commands, exercised against a local web server."""
import csv
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from typer.testing import CliRunner

from scrapewizard.cli.commands.recipe import ALL_PAGES, choose_pages
from scrapewizard.cli.main import app
from scrapewizard.recipe.model import load_recipe

runner = CliRunner()


def page(numbers, next_href=None) -> str:
    cards = "".join(
        f'<div class="product"><h2><a href="/item/{n}">Product number {n}</a></h2>'
        f'<span class="cost">${n}.99</span></div>'
        for n in numbers
    )
    pager = f'<ul class="pager"><li class="next"><a href="{next_href}">next</a></li></ul>' if next_href else ""
    return f"<html><body><main>{cards}</main>{pager}</body></html>"


PAGES = {
    "/": page(range(1, 6), "/page2"),
    "/page2": page(range(6, 11), "/page3"),
    "/page3": page(range(11, 14)),
    "/about": "<html><body><h1>About</h1><p>Just some words here.</p></body></html>",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGES.get(self.path)
        self.send_response(200 if body else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write((body or "not found").encode("utf-8"))

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def in_empty_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_url_alone_saves_data_and_recipe_in_the_current_folder(site, in_empty_folder):
    result = runner.invoke(app, [site + "/", "--yes", "--out", "shop"])

    assert result.exit_code == 0, result.output
    assert "Found 5 items. No browser needed." in result.output
    assert "This list continues on more pages." in result.output

    rows = read_csv(in_empty_folder / "shop.csv")
    assert len(rows) == 5
    assert rows[0] == {"title": "Product number 1", "price": "$1.99", "url": f"{site}/item/1"}

    recipe = load_recipe(in_empty_folder / "shop.recipe.yaml")
    assert recipe.container == "div.product"
    assert recipe.fetch == "http"
    assert recipe.pagination["max_pages"] == 1


def test_all_pages_follows_the_list_to_the_end(site, in_empty_folder):
    result = runner.invoke(app, ["get", site + "/", "--all-pages", "--out", "shop"])

    assert result.exit_code == 0, result.output
    assert len(read_csv(in_empty_folder / "shop.csv")) == 13
    recipe = load_recipe(in_empty_folder / "shop.recipe.yaml")
    assert recipe.pagination["max_pages"] == ALL_PAGES
    assert recipe.checks["min_records"] == 6


def test_pages_option_limits_how_far_it_goes(site, in_empty_folder):
    result = runner.invoke(app, [site + "/", "--pages", "2", "--out", "shop"])
    assert result.exit_code == 0, result.output
    assert len(read_csv(in_empty_folder / "shop.csv")) == 10


def test_json_format(site, in_empty_folder):
    result = runner.invoke(app, [site + "/", "--yes", "--format", "json", "--out", "shop"])
    assert result.exit_code == 0, result.output
    data = json.loads((in_empty_folder / "shop.json").read_text(encoding="utf-8"))
    assert data[0]["title"] == "Product number 1"


def test_run_repeats_a_saved_recipe(site, in_empty_folder):
    runner.invoke(app, [site + "/", "--pages", "2", "--out", "shop"])
    (in_empty_folder / "shop.csv").unlink()

    result = runner.invoke(app, ["run", "shop.recipe.yaml"])

    assert result.exit_code == 0, result.output
    assert "10 rows from 2 pages" in result.output
    assert "all checks passed" in result.output
    assert len(read_csv(in_empty_folder / "shop.csv")) == 10


def test_run_exits_with_an_error_when_a_check_fails(site, in_empty_folder):
    runner.invoke(app, [site + "/", "--yes", "--out", "shop"])
    recipe_file = in_empty_folder / "shop.recipe.yaml"
    recipe_file.write_text(recipe_file.read_text(encoding="utf-8").replace("min_records: 2", "min_records: 99"),
                           encoding="utf-8")

    result = runner.invoke(app, ["run", "shop.recipe.yaml"])

    assert result.exit_code == 1
    assert "Check failed: Expected at least 99 records, got 5." in result.output


def test_without_repair_a_broken_recipe_saves_nothing(site, in_empty_folder):
    runner.invoke(app, [site + "/", "--yes", "--out", "shop"])
    recipe_file = in_empty_folder / "shop.recipe.yaml"
    recipe_file.write_text(recipe_file.read_text(encoding="utf-8").replace("div.product", "div.renamed"),
                           encoding="utf-8")
    (in_empty_folder / "shop.csv").unlink()

    result = runner.invoke(app, ["run", "shop.recipe.yaml", "--no-repair"])

    assert result.exit_code == 1
    assert "No records were found, so nothing was saved." in result.output
    assert not (in_empty_folder / "shop.csv").exists()


def test_missing_recipe_file_is_reported_plainly(in_empty_folder):
    result = runner.invoke(app, ["run", "nothing.recipe.yaml"])
    assert result.exit_code == 1
    assert "Recipe file not found" in result.output


def test_not_a_web_address(in_empty_folder):
    result = runner.invoke(app, ["ftp://nope"])
    assert result.exit_code == 1
    assert "is not a web address" in result.output


def test_unknown_format_is_rejected_before_any_fetching(in_empty_folder):
    result = runner.invoke(app, ["https://example.invalid", "--format", "pdf"])
    assert result.exit_code == 1
    assert "Unknown format 'pdf'" in result.output


def test_unreachable_site_fails_once_without_starting_a_browser(in_empty_folder):
    result = runner.invoke(app, ["http://127.0.0.1:9/", "--yes"])
    assert result.exit_code == 1
    assert result.output.count("Could not connect to the site") == 1
    assert "browser" not in result.output.lower()


@pytest.mark.parametrize("answer, has_more, expected", [
    ("", True, 1),
    ("a", True, ALL_PAGES),
    ("ALL", True, ALL_PAGES),
    ("3", True, 3),
    ("q", True, None),
    ("", False, 1),
    ("a", False, 1),      # nothing more to follow: 'a' just saves
    ("q", False, None),
])
def test_the_one_question(answer, has_more, expected):
    assert choose_pages(has_more, read=lambda prompt: answer) == expected


def test_the_question_treats_closed_input_as_enter():
    def closed(prompt):
        raise EOFError
    assert choose_pages(True, read=closed) == 1
