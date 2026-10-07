"""Following each item into its own page."""
import csv
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from typer.testing import CliRunner

from scrapewizard.cli.main import app
from scrapewizard.recipe.detail import build_detail_fields
from scrapewizard.recipe.extract import extract_detail, parse, read_document_value
from scrapewizard.recipe.model import Field, RecipeError, load_recipe, recipe_from_dict

runner = CliRunner()

ITEMS = {
    n: {"title": f"Product number {n}", "price": f"${n}.99", "sku": f"SKU-{n:04d}", "stock": n * 3,
        "text": f"Product number {n} is described here at some length. " * 5}
    for n in range(1, 7)
}


def list_page() -> str:
    cards = "".join(
        f'<div class="product"><h2><a href="/item/{n}">{item["title"]}</a></h2>'
        f'<span class="cost">{item["price"]}</span></div>'
        for n, item in ITEMS.items()
    )
    return f"<html><body><main>{cards}</main></body></html>"


def item_page(n: int) -> str:
    item = ITEMS[n]
    structured = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "name": "Home"},
        {"@type": "Product", "name": item["title"], "brand": {"@type": "Brand", "name": f"Brand {n}"},
         "offers": {"@type": "Offer", "price": item["price"].lstrip("$"), "priceCurrency": "USD"}},
    ]}
    return f"""<html><head><meta name="description" content="Buy things here."></head><body>
      <nav><p>{'Site navigation text that is long but is not the description. ' * 4}</p></nav>
      <h1>{item["title"]}</h1>
      <script type="application/ld+json">{json.dumps(structured)}</script>
      <div id="about"><h2>About</h2></div>
      <p>{item["text"]}</p>
      <table>
        <tr><th>SKU</th><td>{item["sku"]}</td></tr>
        <tr><th>Price</th><td>{item["price"]}</td></tr>
        <tr><th>In stock:</th><td>{item["stock"]}</td></tr>
        <tr><th>Category</th><td>Gadgets</td></tr>
      </table>
    </body></html>"""


def list_record(n: int) -> dict:
    return {"title": ITEMS[n]["title"], "price": ITEMS[n]["price"], "url": f"https://shop.test/item/{n}"}


# --- learning the fields ------------------------------------------------------

def learned():
    pages = [parse(item_page(n)) for n in (1, 2, 3)]
    return build_detail_fields(pages, [list_record(n) for n in (1, 2, 3)], ["title", "price", "url"])


def test_labelled_rows_become_named_fields():
    fields = {f.name: f for f in learned()}
    assert fields["sku"].select == ['th:-soup-contains("SKU") + td']
    assert fields["in_stock"].type == "number"       # the label's colon is dropped
    assert fields["category"].select == ['th:-soup-contains("Category") + td']   # same on every page, still data


def test_values_the_list_already_has_are_not_collected_again():
    names = [f.name for f in learned()]
    assert "heading" not in names            # the h1 repeats the list's title
    assert "price_detail" not in names       # the Price row repeats the list's price
    assert "name" not in names               # so does the structured data's name


def test_structured_data_is_read_and_site_wide_values_are_dropped():
    fields = {f.name: f for f in learned()}
    assert fields["brand_name"].select == ["jsonld:brand.name"]
    assert "price_currency" not in fields    # "USD" on every page: not item data
    assert "price_detail" not in fields      # "2.99" is the list's "$2.99" again


def test_description_is_the_main_text_not_the_navigation():
    description = next(f for f in learned() if f.name == "description")
    assert description.select == ["#about + p"]


def test_reading_an_item_page():
    soup = parse(item_page(2))
    assert read_document_value(soup, "jsonld:brand.name") == "Brand 2"
    assert read_document_value(soup, "jsonld:offers.price") == "2.99"
    assert read_document_value(soup, "jsonld:nothing.here") is None
    assert read_document_value(soup, "meta:description") == "Buy things here."
    assert read_document_value(soup, 'th:-soup-contains("SKU") + td') == "SKU-0002"
    record = extract_detail(soup, [Field("sku", ["td.missing", 'th:-soup-contains("SKU") + td']),
                                   Field("in_stock", ['th:-soup-contains("In stock") + td'], "number")],
                            "https://shop.test/item/2")
    assert record == {"sku": "SKU-0002", "in_stock": 6}


def test_broken_structured_data_is_skipped():
    soup = parse('<script type="application/ld+json">{not json</script><p>x</p>')
    assert read_document_value(soup, "jsonld:name") is None


def test_no_pages_gives_no_fields():
    assert build_detail_fields([], [], []) == []


# --- the recipe ---------------------------------------------------------------

def test_detail_must_follow_a_field_of_the_list():
    data = {"name": "x", "url": "u", "collection": {"container": "div", "fields": {"title": "a"}},
            "detail": {"follow": "link", "fields": {"sku": "td"}}}
    with pytest.raises(RecipeError, match="not one of the list's fields"):
        recipe_from_dict(data)
    with pytest.raises(RecipeError, match="needs 'follow'"):
        recipe_from_dict(dict(data, detail={"fields": {"sku": "td"}}))


# --- the command ----------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body = list_page()
        elif self.path.startswith("/item/") and self.path[6:].isdigit() and int(self.path[6:]) in ITEMS:
            body = None if self.path == "/item/5" else item_page(int(self.path[6:]))   # item 5 is broken
        else:
            body = None
        self.send_response(200 if body else 500)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write((body or "error").encode("utf-8"))

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_follow_adds_item_page_fields_to_every_row(site, folder):
    result = runner.invoke(app, [site + "/", "--follow", "--yes", "--out", "shop"])

    assert result.exit_code == 0, result.output
    assert "Opening 3 item pages to see what they hold ..." in result.output
    assert "Each item page adds" in result.output
    assert "item pages: 6 of 6" in result.output

    data = rows(folder / "shop.csv")
    assert len(data) == 6
    assert data[0]["sku"] == "SKU-0001"
    assert data[0]["in_stock"] == "3"
    assert data[0]["brand_name"] == "Brand 1"
    assert data[0]["description"].startswith("Product number 1 is described here")
    # Item 5's page fails: the row is kept, with its item-page fields empty.
    assert data[4]["title"] == "Product number 5" and data[4]["sku"] == ""

    recipe = load_recipe(folder / "shop.recipe.yaml")
    assert recipe.follow == "url"
    assert "sku" in [f.name for f in recipe.detail_fields]


def test_a_saved_recipe_follows_item_pages_again(site, folder):
    runner.invoke(app, [site + "/", "--follow", "--yes", "--out", "shop"])
    (folder / "shop.csv").unlink()

    result = runner.invoke(app, ["run", "shop.recipe.yaml"])

    assert result.exit_code == 0, result.output
    assert "0 new, 0 changed, 0 removed since last run" in result.output
    assert rows(folder / "shop.csv")[1]["sku"] == "SKU-0002"


def test_without_follow_item_pages_are_not_opened(site, folder):
    result = runner.invoke(app, [site + "/", "--yes", "--out", "shop"])
    assert "item pages" not in result.output
    assert list(rows(folder / "shop.csv")[0]) == ["title", "price", "url"]
    assert load_recipe(folder / "shop.recipe.yaml").follow is None
