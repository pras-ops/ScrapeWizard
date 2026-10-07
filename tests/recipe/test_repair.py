"""Run memory, change summaries and self-repair, against a site whose pages can be swapped."""
import csv
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from typer.testing import CliRunner

from scrapewizard.cli.main import app
from scrapewizard.recipe.heal import RepairRefused, repair, what_broke
from scrapewizard.recipe.model import Field, Recipe, load_recipe
from scrapewizard.recipe.state import compare, key_field, load_state, make_state

runner = CliRunner()

ITEMS = [(n, f"Product number {n}", f"${n}.99") for n in range(1, 9)]


def original(items=ITEMS) -> str:
    cards = "".join(
        f'<div class="product"><h2><a href="/item/{n}">{title}</a></h2><span class="cost">{price}</span></div>'
        for n, title, price in items
    )
    return f"<html><body><main>{cards}</main></body></html>"


def redesigned(items=ITEMS, with_price=True) -> str:
    """Same items, different tags, classes and nesting."""
    cards = "".join(
        f'<li class="card"><section class="info"><a class="name" href="/item/{n}">{title}</a>'
        + (f'<em class="amount">{price}</em>' if with_price else "")
        + "</section></li>"
        for n, title, price in items
    )
    return f"<html><body><ul class='grid'>{cards}</ul></body></html>"


class Site:
    def __init__(self):
        self.pages = {}
        site = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = site.pages.get(self.path)
                self.send_response(200 if body else 404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write((body or "not found").encode("utf-8"))

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/"


@pytest.fixture
def site():
    s = Site()
    s.pages["/"] = original()
    yield s
    s.server.shutdown()


@pytest.fixture(autouse=True)
def folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build(site):
    result = runner.invoke(app, [site.url, "--yes", "--out", "shop"])
    assert result.exit_code == 0, result.output


# --- the commands -----------------------------------------------------------

def test_first_run_is_remembered(site, folder):
    build(site)
    state = load_state(folder / "shop.recipe.yaml")
    assert state["count"] == 8
    assert state["key"] == "url"
    assert state["fill"] == {"title": 1.0, "price": 1.0, "url": 1.0}
    assert (folder / ".scrapewizard" / "shop.state.json").exists()


def test_a_redesign_is_repaired_and_checked_against_the_last_run(site, folder):
    build(site)
    before = rows(folder / "shop.csv")
    site.pages["/"] = redesigned()

    result = runner.invoke(app, ["run", "shop.recipe.yaml"])

    assert result.exit_code == 0, result.output
    assert "No records were found." in result.output
    # The builder prefers the innermost block that holds the whole record.
    assert "Repaired: list: div.product -> section.info" in result.output
    assert "Repaired: price: span.cost -> em.amount" in result.output
    assert "Checked:  8 rows on the first page, 8 of them known from the last run." in result.output
    assert "Recipe updated." in result.output
    assert "all checks passed" in result.output
    # Same data as before the redesign, under the same column names.
    assert rows(folder / "shop.csv") == before

    recipe = load_recipe(folder / "shop.recipe.yaml")
    assert recipe.container == "section.info"
    price = next(f for f in recipe.fields if f.name == "price")
    assert price.select[0] == "em.amount" and "span.cost" in price.select  # old selector kept as a fallback
    assert "8 known items found again" in recipe.history[-1]["checked"]


def test_one_changed_field_is_repaired(site, folder):
    build(site)
    site.pages["/"] = original().replace('class="cost"', 'class="sale-price"')

    result = runner.invoke(app, ["run", "shop.recipe.yaml"])

    assert result.exit_code == 0, result.output
    assert '"price" stopped matching (0 of 8 rows).' in result.output
    assert "Repaired: price: span.cost -> span.sale-price" in result.output
    assert "list:" not in result.output  # the list itself did not move
    assert rows(folder / "shop.csv")[0]["price"] == "$1.99"


def test_a_repair_that_cannot_find_a_required_field_is_refused(site, folder):
    build(site)
    (folder / "shop.csv").unlink()
    site.pages["/"] = redesigned(with_price=False)

    result = runner.invoke(app, ["run", "shop.recipe.yaml"])

    assert result.exit_code == 1
    assert "It could not be repaired safely" in result.output
    assert "Nothing was saved." in result.output
    assert not (folder / "shop.csv").exists()
    assert load_recipe(folder / "shop.recipe.yaml").container == "div.product"  # recipe left untouched


def test_a_page_with_no_list_is_refused(site, folder):
    build(site)
    site.pages["/"] = "<html><body><h1>We moved</h1><p>This shop has closed.</p></body></html>"

    result = runner.invoke(app, ["run", "shop.recipe.yaml"])

    assert result.exit_code == 1
    assert "It could not be repaired safely: no repeating list was found on the page." in result.output


def test_changes_since_the_last_run_are_summarised(site, folder):
    build(site)
    changed = [(n, t, p) for n, t, p in ITEMS if n != 3]          # one removed
    changed[0] = (1, "Product number 1", "$0.50")                  # one price changed
    changed.append((9, "Product number 9", "$9.99"))               # one new
    site.pages["/"] = original(changed)

    result = runner.invoke(app, ["run", "shop.recipe.yaml"])

    assert result.exit_code == 0, result.output
    assert "8 rows from 1 page   1 new, 1 changed, 1 removed since last run" in result.output

    again = runner.invoke(app, ["run", "shop.recipe.yaml"])
    assert "0 new, 0 changed, 0 removed since last run" in again.output


# --- the pieces --------------------------------------------------------------

def recipe() -> Recipe:
    return Recipe(
        name="shop", url="https://shop.test/", container="div.product",
        fields=[Field("title", ["h2 > a"]), Field("price", ["span.cost"], "money"), Field("url", ["h2 > a@href"], "url")],
        checks={"min_records": 4, "required": ["title", "price"]},
    )


def records(items=ITEMS):
    return [{"title": t, "price": p, "url": f"https://shop.test/item/{n}"} for n, t, p in items]


def test_what_broke():
    r = recipe()
    assert what_broke(records(), r, None) is None
    assert what_broke([], r, None) == "No records were found."
    no_price = [dict(row, price=None) for row in records()]
    assert what_broke(no_price, r, None) == '"price" stopped matching (0 of 8 rows).'
    # An optional field that used to be filled and now is not, known only from memory.
    r.checks["required"] = ["title"]
    assert what_broke(no_price, r, {"fill": {"price": 1.0}}) == '"price" stopped matching (0 of 8 rows).'
    assert what_broke(no_price, r, {"fill": {"price": 0.3}}) is None


def test_repair_without_memory_needs_every_field_to_match_by_name():
    fix = repair(recipe(), redesigned(), "https://shop.test/", None)
    assert fix.verified is False
    assert fix.recipe.container == "section.info"
    assert fix.records[0] == {"title": "Product number 1", "price": "$1.99", "url": "https://shop.test/item/1"}


def test_repair_is_verified_even_when_every_price_changed():
    state = make_state(recipe(), records(), 1)
    repriced = [(n, t, f"${n}.49") for n, t, _ in ITEMS]
    fix = repair(recipe(), redesigned(repriced), "https://shop.test/", state)
    assert fix.verified is True and fix.matched == 8
    assert fix.records[0]["price"] == "$1.49"


def test_repair_refuses_when_nothing_changed_on_the_page():
    """If the page still matches the recipe exactly, there is nothing to repair."""
    from scrapewizard.recipe.builder import build_recipe
    built = build_recipe(original(), "https://shop.test/").recipe
    with pytest.raises(RepairRefused, match="data itself seems to be missing"):
        repair(built, original(), "https://shop.test/", None)


def test_key_field_and_compare():
    r = recipe()
    assert key_field(r, records()) == "url"
    state = make_state(r, records(), 1)
    assert str(compare(state, records(), 1)) == "0 new, 0 changed, 0 removed since last run"
    assert compare(state, records(), 5) is None      # a different page limit is not comparable
    assert compare(None, records(), 1) is None       # no memory
