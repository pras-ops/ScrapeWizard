"""The builder must find the right list and sensible fields with no LLM.

Each fixture reproduces a page shape that went wrong at some point during
development against live sites.
"""
from scrapewizard.recipe.builder import build_recipe, default_name

URL = "https://shop.test/catalogue/"

BOOKS = [
    ("A Light in the Attic and Other Poems", "£51.77", "a-light"),
    ("Tipping the Velvet", "£53.74", "tipping"),
    ("Soumission", "£50.10", "soumission"),
    ("Sharp Objects", "£47.82", "sharp"),
    ("Sapiens: A Brief History of Humankind", "£54.23", "sapiens"),
    ("The Requiem Red", "£22.65", "requiem"),
]


def shorten(title: str) -> str:
    return title if len(title) <= 18 else title[:15] + "..."


def shop_page() -> str:
    """Cards inside layout-grid wrappers, a big category menu, and a pager."""
    cards = "".join(
        f"""<li class="col-xs-6 col-sm-4"><article class="product_pod">
              <div class="image_container"><a href="{slug}/index.html">
                <img class="thumbnail" src="/media/{slug}.jpg" alt="{title}"></a></div>
              <h3><a href="{slug}/index.html" title="{title}">{shorten(title)}</a></h3>
              <p class="price_color">{price}</p>
              <p class="availability">In stock</p>
              <button class="btn">Add to basket</button>
            </article></li>"""
        for title, price, slug in BOOKS
    )
    menu = "".join(f'<li><a href="/category/{n}">Category number {n}</a></li>' for n in range(40))
    return f"""<html><head><title>Shop</title></head><body>
        <div class="side_categories"><ul class="nav nav-list">{menu}</ul></div>
        <section><ol class="row">{cards}</ol></section>
        <ul class="pager"><li class="next"><a href="page-2.html">next</a></li></ul>
        </body></html>"""


def test_picks_the_cards_not_the_menu_or_the_grid_wrapper():
    result = build_recipe(shop_page(), URL)
    assert result is not None
    assert result.recipe.container == "article.product_pod"
    assert len(result.records) == len(BOOKS)


def test_fields_are_named_typed_and_free_of_noise():
    result = build_recipe(shop_page(), URL)
    fields = {f.name: f for f in result.recipe.fields}

    # Readable columns first; links and image addresses last.
    # "In stock" repeats on every card but is data; "Add to basket" is a button and is not.
    assert list(fields) == ["title", "price", "availability", "url", "image"]
    assert result.records[0]["availability"] == "In stock"
    assert fields["price"].type == "money"
    assert fields["url"].type == "url"
    assert fields["image"].type == "image"
    # The full title comes from the attribute, not the cut-off link text.
    assert fields["title"].select == ["h3 > a@title"]
    # Two links lead to the same place: both are kept as a ladder.
    assert fields["url"].select == ["div.image_container > a@href", "h3 > a@href"]

    first = result.records[0]
    assert first["title"] == "A Light in the Attic and Other Poems"
    assert first["price"] == "£51.77"
    assert first["url"] == "https://shop.test/catalogue/a-light/index.html"
    assert first["image"] == "https://shop.test/media/a-light.jpg"


def test_pagination_and_checks_are_filled_in():
    result = build_recipe(shop_page(), URL)
    assert result.next_url == "https://shop.test/catalogue/page-2.html"
    assert result.recipe.pagination == {"type": "next_link", "select": "li.next > a", "max_pages": 1}
    assert result.recipe.checks == {"min_records": 3, "required": ["title", "price"]}


def quotes_page() -> str:
    """Each item holds a variable-length list of tags: the item is the record, not the tags."""
    quotes = [
        ("The world as we have created it is a process of our thinking.", "Albert Einstein", ["change", "thinking", "world"]),
        ("It is our choices that show what we truly are.", "J.K. Rowling", ["abilities", "choices"]),
        ("There are only two ways to live your life.", "Albert Camus", ["life"]),
        ("The person who has not pleasure in a good novel is stupid.", "Jane Austen", ["books", "humor", "classic", "novels"]),
    ]
    blocks = "".join(
        f"""<div class="quote"><span class="text">{text}</span>
            <span>by <small class="author">{author}</small> <a href="/author/{author.split()[-1]}">(about)</a></span>
            <div class="tags">Tags: {''.join(f'<a class="tag" href="/tag/{t}/">{t}</a> ' for t in tags)}</div></div>"""
        for text, author, tags in quotes
    )
    return f"<html><body><div class='col-md-8'>{blocks}</div></body></html>"


def test_item_with_a_sublist_is_the_record():
    result = build_recipe(quotes_page(), "https://quotes.test/")
    assert result.recipe.container == "div.quote"
    assert len(result.records) == 4
    names = [f.name for f in result.recipe.fields]
    assert names == ["text", "author", "tags", "url"]
    assert result.records[1]["author"] == "J.K. Rowling"
    assert result.records[1]["tags"] == "Tags: abilities choices"


def table_page(with_classes: bool) -> str:
    teams = [("Boston Bruins", 44, 24, "0.55"), ("Buffalo Sabres", 31, 30, "0.388"),
             ("Calgary Flames", 46, 26, "0.575"), ("Chicago Blackhawks", 49, 23, "0.613")]
    def cell(cls, value):
        return f'<td class="{cls}">{value}</td>' if with_classes else f"<td>{value}</td>"
    rows = "".join(
        f"<tr{' class=\"team\"' if with_classes else ''}>{cell('name', n)}{cell('wins', w)}{cell('gf', l)}{cell('pct', p)}</tr>"
        for n, w, l, p in teams
    )
    return f"""<html><body><table id="stats"><thead><tr><th>Team</th><th>W</th><th>GF</th><th>Pct</th></tr></thead>
               <tbody>{rows}</tbody></table></body></html>"""


def test_table_rows_with_classed_cells_use_the_class_names():
    result = build_recipe(table_page(with_classes=True), "https://stats.test/")
    assert result.recipe.container == "tr.team"
    assert [f.name for f in result.recipe.fields] == ["name", "wins", "gf", "pct"]
    assert result.records[0] == {"name": "Boston Bruins", "wins": 44, "gf": 24, "pct": 0.55}


def test_plain_table_rows_are_found_by_position():
    result = build_recipe(table_page(with_classes=False), "https://stats.test/")
    assert result is not None
    assert result.recipe.container == "#stats > tbody > tr"
    assert len(result.records) == 4
    assert len(result.recipe.fields) == 4
    assert "Boston Bruins" in result.records[0].values()
    assert 44 in result.records[0].values()


def test_generated_class_names_are_not_used_as_selectors():
    cards = "".join(
        f'<div class="css-1x2y3z card"><h2 class="sc-bdVaJa">Item {i} name here</h2>'
        f'<span class="mt-4 cost">${i}9.99</span></div>'
        for i in range(1, 6)
    )
    result = build_recipe(f"<html><body><main>{cards}</main></body></html>", "https://x.test/")
    recipe_text = str(result.recipe.to_dict())
    for generated in ("css-1x2y3z", "sc-bdVaJa", "mt-4"):
        assert generated not in recipe_text
    assert result.recipe.container == "div.card"
    assert result.records[0] == {"title": "Item 1 name here", "price": "$19.99"}


def two_lists_page() -> str:
    posts = "".join(
        f'<article class="post"><h2><a href="/p/{i}">Long article headline number {i}</a></h2>'
        f'<p class="summary">Summary text for article {i} goes here.</p></article>'
        for i in range(1, 6)
    )
    jobs = "".join(
        f'<div class="job"><span class="role">Engineer level {i}</span><span class="city">City {i}</span>'
        f'<span class="pay">${i}0,000</span><span class="team">Team {i}</span></div>'
        for i in range(1, 9)
    )
    return f"<html><body><section>{posts}</section><section>{jobs}</section></body></html>"


def test_example_values_choose_between_lists():
    page = two_lists_page()
    assert build_recipe(page, "https://x.test/").recipe.container == "div.job"

    by_example = build_recipe(page, "https://x.test/", likes=["Long article headline number 3"])
    assert by_example.recipe.container == "article.post"
    assert by_example.recipe.fields[0].name == "title"
    assert by_example.records[2]["title"] == "Long article headline number 3"


def test_example_value_not_on_the_page_gives_nothing():
    assert build_recipe(two_lists_page(), "https://x.test/", likes=["not on this page"]) is None


def test_state_classes_get_a_simpler_fallback_selector():
    """An out-of-stock item has no 'instock' class: the ladder must still find its status."""
    cards = "".join(
        f'<div class="item"><h3>Thing number {i}</h3><p class="instock availability">In stock</p>'
        f'<span class="cost">${i}.00</span></div>'
        for i in range(1, 7)
    )
    result = build_recipe(f"<html><body><main>{cards}</main></body></html>", "https://x.test/")
    availability = next(f for f in result.recipe.fields if f.name == "availability")
    # Most specific first, then the descriptive class alone, then the state class as a last resort.
    assert availability.select == ["p.instock.availability", "p.availability", "p.instock"]

    from scrapewizard.recipe.extract import extract_records, parse
    changed = cards.replace('<p class="instock availability">In stock</p>',
                            '<p class="outofstock availability">Sold out</p>', 1)
    records = extract_records(parse(f"<html><body><main>{changed}</main></body></html>"),
                              result.recipe, "https://x.test/")
    assert records[0]["availability"] == "Sold out"
    assert records[1]["availability"] == "In stock"


def test_page_without_a_list_gives_nothing():
    page = "<html><body><h1>About us</h1><p>We are a company.</p><p>Contact us.</p></body></html>"
    assert build_recipe(page, "https://x.test/about") is None


def test_default_name_comes_from_the_host():
    assert default_name("https://books.toscrape.com/catalogue/") == "books"
    assert default_name("https://www.example.com/") == "example"
    assert default_name("http://127.0.0.1:8000/") == "data"
