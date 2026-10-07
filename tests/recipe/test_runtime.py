import pytest

from scrapewizard.recipe.extract import evaluate_checks, extract_records, parse, run_recipe, split_selector
from scrapewizard.recipe.model import Field, Recipe, RecipeError, load_recipe, recipe_from_dict, save_recipe
from scrapewizard.recipe.types import convert, infer_type

PAGE_1 = """
<html><body>
<div class="product"><h3><a href="/item/1" title="The Long Title One">The Long…</a></h3>
  <span class="cost">$10.50</span><span class="qty">1,200</span></div>
<div class="product"><h3><a href="/item/2" title="The Long Title Two">The Long…</a></h3>
  <span class="cost">$7.00</span><span class="qty">15</span></div>
<ul class="pager"><li class="next"><a href="/list?page=2">next</a></li></ul>
</body></html>
"""
PAGE_2 = """
<html><body>
<div class="product"><h3><a href="/item/3" title="The Long Title Three">The Long…</a></h3>
  <span class="cost">$3.25</span><span class="qty">8</span></div>
</body></html>
"""
PAGES = {"https://shop.test/list": PAGE_1, "https://shop.test/list?page=2": PAGE_2}


def make_recipe(**overrides) -> Recipe:
    settings = dict(
        name="shop",
        url="https://shop.test/list",
        container="div.product",
        fields=[
            # First selector does not exist: the ladder falls through to the second.
            Field("title", ["h3 a.missing@title", "h3 a@title"], "text"),
            Field("price", ["span.cost"], "money"),
            Field("stock", ["span.qty"], "number"),
            Field("url", ["h3 a@href"], "url"),
        ],
        pagination={"type": "next_link", "select": "li.next > a", "max_pages": 5},
        checks={"min_records": 3, "required": ["title", "price"]},
    )
    settings.update(overrides)
    return Recipe(**settings)


def fake_fetch(url: str, mode: str) -> str:
    return PAGES[url]


def test_extract_reads_text_attributes_and_types():
    records = extract_records(parse(PAGE_1), make_recipe(), "https://shop.test/list")
    assert records[0] == {
        "title": "The Long Title One",
        "price": "$10.50",
        "stock": 1200,
        "url": "https://shop.test/item/1",
    }
    assert len(records) == 2


def test_run_follows_pagination_and_passes_checks():
    result = run_recipe(make_recipe(), fetcher=fake_fetch, delay=0)
    assert result.pages == 2
    assert [r["title"] for r in result.records] == [
        "The Long Title One", "The Long Title Two", "The Long Title Three",
    ]
    assert result.ok


def test_run_respects_max_pages():
    result = run_recipe(make_recipe(), max_pages=1, fetcher=fake_fetch, delay=0)
    assert result.pages == 1
    assert len(result.records) == 2
    assert result.failures == ["Expected at least 3 records, got 2."]


def test_stale_pagination_selector_falls_back_to_detection():
    recipe = make_recipe(pagination={"type": "next_link", "select": "a.gone", "max_pages": 5})
    assert run_recipe(recipe, fetcher=fake_fetch, delay=0).pages == 2


def test_required_field_coverage_check():
    recipe = make_recipe(fields=[Field("title", ["h3 a@title"]), Field("sku", ["span.sku"])],
                         checks={"required": ["sku"]})
    records = extract_records(parse(PAGE_1), recipe, recipe.url)
    assert evaluate_checks(records, recipe) == ["'sku' is filled in only 0 of 2 records."]


def test_invalid_container_selector_is_reported_plainly():
    with pytest.raises(RecipeError, match="not valid CSS"):
        extract_records(parse(PAGE_1), make_recipe(container="div..bad["), "https://shop.test/")


def test_split_selector():
    assert split_selector("h3 a@title") == ("h3 a", "title")
    assert split_selector("@href") == ("", "href")
    assert split_selector("p.price") == ("p.price", None)
    assert split_selector('a[href*="@"]') == ('a[href*="@"]', None)


def test_recipe_round_trips_through_yaml(tmp_path):
    path = save_recipe(make_recipe(), tmp_path / "shop.recipe.yaml")
    loaded = load_recipe(path)
    assert loaded == make_recipe()


@pytest.mark.parametrize("data, message", [
    ({"name": "x", "url": "u"}, "missing 'collection'"),
    ({"name": "x", "url": "u", "collection": {"container": "div", "fields": {}}}, "at least one field"),
    ({"name": "x", "url": "u", "collection": {"container": "div", "fields": {"a": {"select": "p", "type": "nope"}}}}, "unknown type"),
    ({"name": "x", "url": "u", "fetch": "ftp", "collection": {"container": "div", "fields": {"a": "p"}}}, "'fetch' must be"),
])
def test_invalid_recipes_give_plain_errors(data, message):
    with pytest.raises(RecipeError, match=message):
        recipe_from_dict(data)


def test_field_shorthand_string_is_accepted():
    recipe = recipe_from_dict({"name": "x", "url": "u", "collection": {"container": "li", "fields": {"t": "a"}}})
    assert recipe.fields == [Field("t", ["a"], "text")]


@pytest.mark.parametrize("values, expected", [
    (["£51.77", "£53.74", "£50.10"], "money"),
    (["12.50 €", "9 EUR"], "money"),
    (["1,200", "15", "8"], "number"),
    (["2024-01-31", "2024-02-01"], "date"),
    (["Jan 5, 2024", "March 12, 2023"], "date"),
    (["a@b.com", "c@d.org"], "email"),
    (["In stock", "In stock", "Sold out"], "text"),
    ([], "text"),
])
def test_infer_type(values, expected):
    assert infer_type(values) == expected


def test_convert():
    assert convert("  A   B ", "text") == "A B"
    assert convert("", "text") is None
    assert convert("/a/b", "url", "https://x.test/c/") == "https://x.test/a/b"
    assert convert("1,200", "number") == 1200
    assert convert("3.5", "number") == 3.5
    assert convert("n/a", "number") == "n/a"
