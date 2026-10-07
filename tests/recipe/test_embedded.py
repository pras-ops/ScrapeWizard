"""Lists that a page ships as data in a script, read with no browser and no selectors."""
import json

from scrapewizard.recipe.builder import build_recipe
from scrapewizard.recipe.embedded import data_items, dig, embedded_data, find_lists, read_data_value
from scrapewizard.recipe.extract import extract_records, parse
from scrapewizard.recipe.heal import repair
from scrapewizard.recipe.state import make_state

URL = "https://shop.test/laptops"

PRODUCTS = [
    {"id": 100 + n, "__typename": "Product", "name": f"Laptop model {n} with a long name", "slug": f"/p/laptop-{n}",
     "brand": {"name": ["Acme", "Globex", "Initech"][n % 3]}, "price": {"amount": 499.0 + n * 50, "currency": "USD"},
     "inStock": n % 2 == 0, "tags": ["new", f"series-{n}"],
     "images": [{"url": f"https://cdn.shop.test/img/{n}.jpg", "alt": "front"}],
     "token": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"}
    for n in range(1, 9)
]
MENU = [{"label": "Home", "href": "/"}, {"label": "Deals", "href": "/deals"}, {"label": "Help", "href": "/help"}]


def next_page(products=PRODUCTS, key="products") -> str:
    """A page drawn by JavaScript: the HTML holds a menu and an empty root, the data is in a script."""
    state = {"props": {"pageProps": {key: products, "menu": MENU, "total": len(products)}}, "buildId": "abc"}
    return f"""<html><body><nav><a href="/">Home</a><a href="/deals">Deals</a><a href="/help">Help</a></nav>
        <div id="__next"></div>
        <script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script></body></html>"""


def test_list_is_read_from_the_page_data_when_the_html_shows_only_a_menu():
    result = build_recipe(next_page(), URL)
    assert result is not None
    assert result.recipe.container == "data:props.pageProps.products"
    assert not result.in_menu
    fields = {f.name: (f.select[0], f.type) for f in result.recipe.fields}
    assert fields == {
        "title": ("name", "text"),
        "id": ("id", "number"),
        "brand": ("brand.name", "text"),              # like author.name: the outer key is the column
        "price_amount": ("price.amount", "number"),
        "tags": ("tags", "text"),
        "url": ("slug", "url"),
        "image": ("images.0.url", "image"),
    }
    first = result.records[0]
    assert first["title"] == "Laptop model 1 with a long name"
    assert first["price_amount"] == 549.0
    assert first["url"] == "https://shop.test/p/laptop-1"
    assert first["image"] == "https://cdn.shop.test/img/1.jpg"
    assert first["tags"] == "new, series-1"
    assert len(result.records) == 8


def test_columns_leave_out_constants_internal_keys_and_tokens():
    result = build_recipe(next_page(), URL)
    names = [f.name for f in result.recipe.fields]
    assert names[0] == "title"
    assert names[-2:] == ["url", "image"]            # addresses last
    for unwanted in ("typename", "token", "price_currency", "images_alt", "in_stock"):
        assert unwanted not in names


def test_a_list_in_the_html_is_preferred_over_page_data():
    cards = "".join(
        f'<div class="product"><h2><a href="/p/laptop-{n}">Laptop model {n}</a></h2><span class="cost">${n}99</span></div>'
        for n in range(1, 9)
    )
    page = next_page().replace('<div id="__next"></div>', f"<main>{cards}</main>")
    assert build_recipe(page, URL).recipe.container == "div.product"


def test_menu_is_returned_and_marked_when_there_is_nothing_else():
    page = '<html><body><nav><a href="/a">Home page</a><a href="/b">The deals</a><a href="/c">Get help</a></nav></body></html>'
    result = build_recipe(page, URL)
    assert result is not None and result.in_menu


def test_example_value_picks_the_list_in_the_data():
    reviews = [{"author": f"Reader {n}", "text": f"Review text number {n}, a full sentence.", "stars": n % 5 + 1,
                "date": f"2026-09-{n:02d}"} for n in range(1, 13)]
    state = {"props": {"pageProps": {"products": PRODUCTS, "reviews": reviews}}}
    page = f'<html><body><div id="app"></div><script type="application/json">{json.dumps(state)}</script></body></html>'
    assert build_recipe(page, URL, likes=["Review text number 3"]).recipe.container == "data:props.pageProps.reviews"
    assert build_recipe(page, URL, likes=["Laptop model 2"]).recipe.container == "data:props.pageProps.products"
    assert build_recipe(page, URL, likes=["not anywhere"]) is None


def test_data_assigned_to_a_variable_in_a_script_is_read():
    page = f"""<html><body><div id="app"></div>
        <script>window.dataLayer = []; window.__STATE__ = {json.dumps({"catalog": {"items": PRODUCTS}})};
        window.other = function() {{ return 1; }};</script></body></html>"""
    result = build_recipe(page, URL)
    assert result.recipe.container == "data:catalog.items"
    assert len(result.records) == 8


def test_search_engine_item_list_is_unwrapped():
    listing = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": n, "item": {"@type": "Recipe", "name": f"Soup recipe number {n}",
                                                         "url": f"https://food.test/r/{n}", "cookTime": f"PT{n * 5}M",
                                                         "author": {"@type": "Person", "name": f"Cook {n}"}}}
        for n in range(1, 7)]}
    page = f'<html><body><script type="application/ld+json">{json.dumps(listing)}</script></body></html>'
    result = build_recipe(page, "https://food.test/")
    assert result.recipe.container == "data:itemListElement"
    assert result.records[1] == {
        "title": "Soup recipe number 2", "position": 2, "cook_time": "PT10M", "author": "Cook 2",
        "url": "https://food.test/r/2",
    }


def test_small_settings_lists_are_not_mistaken_for_the_data():
    state = {"menu": MENU, "locales": [{"code": "en", "name": "English"}, {"code": "fr", "name": "French"},
                                         {"code": "de", "name": "German"}]}
    page = f'<html><body><div id="app"></div><script type="application/json">{json.dumps(state)}</script></body></html>'
    assert find_lists(parse(page)) == []   # two columns each: a menu and a language picker, not records
    assert build_recipe(page, URL) is None


def test_broken_json_and_code_are_skipped():
    page = """<html><body><script type="application/json">{"broken": </script>
              <script>var config = {unquoted: 1, list: [1, 2, 3]};</script></body></html>"""
    assert embedded_data(parse(page)) == []


def test_reading_paths():
    entry = {"a": {"b": [{"c": "deep"}, {"c": "second"}]}, "n": 3, "flag": True, "tags": ["x", "y"], "obj": {"k": 1}}
    assert dig(entry, "a.b.1.c") == "second"
    assert dig(entry, "a.b.5.c") is None
    assert dig(entry, "a.missing.c") is None
    assert read_data_value(entry, "a.b.0.c") == "deep"
    assert read_data_value(entry, "n") == "3"
    assert read_data_value(entry, "tags") == "x, y"
    assert read_data_value(entry, "flag") is None      # true/false is not a value to show
    assert read_data_value(entry, "obj") is None


def test_running_a_data_recipe_reads_the_next_delivery_of_the_same_page():
    recipe = build_recipe(next_page(), URL).recipe
    later = [dict(p, name=p["name"] + " (2027)") for p in PRODUCTS[:5]]
    records = extract_records(parse(next_page(later)), recipe, URL)
    assert [r["title"] for r in records][:2] == ["Laptop model 1 with a long name (2027)",
                                                 "Laptop model 2 with a long name (2027)"]
    assert data_items(parse("<html><body></body></html>"), recipe.container) == []


def test_repair_follows_the_list_to_its_new_place_in_the_data():
    built = build_recipe(next_page(), URL)
    state = make_state(built.recipe, built.records, 1)

    moved = next_page(key="catalogItems")          # the site renamed the key
    assert extract_records(parse(moved), built.recipe, URL) == []

    fixed = repair(built.recipe, moved, URL, state)
    assert fixed.verified
    assert fixed.recipe.container == "data:props.pageProps.catalogItems"
    assert [r["title"] for r in fixed.records] == [r["title"] for r in built.records]


def test_a_nested_name_or_link_is_not_taken_for_the_entry_itself():
    quotes = [{"text": f"A saying worth writing down, number {n}.", "tags": ["life", f"t{n}"],
               "author": {"name": ["Ann Author", "Bob Writer"][n % 2], "link": f"https://people.test/{n % 2}"}}
              for n in range(1, 11)]
    page = f"<html><body><div id='quotes'></div><script>var data = {json.dumps(quotes)}; render(data);</script></body></html>"
    result = build_recipe(page, "https://quotes.test/js/")
    assert result.recipe.container == "data:"          # the data is the list itself
    assert [f.name for f in result.recipe.fields] == ["text", "tags", "author", "author_link"]
    assert result.records[0] == {
        "text": "A saying worth writing down, number 1.", "tags": "life, t1",
        "author": "Bob Writer", "author_link": "https://people.test/1",
    }
