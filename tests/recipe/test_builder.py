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


# --- Shapes met on live sites that the first version of the builder got wrong ---

PAPERS = [
    ("2401.00001", "Learning to Rank Search Results with Small Models", "Ada Lovelace, Alan Turing", "Machine Learning"),
    ("2401.00002", "A Survey of Web Data Extraction Methods", "Grace Hopper", "Information Retrieval"),
    ("2401.00003", "Fast Tree Matching for Document Layouts", "Edsger Dijkstra, Barbara Liskov", "Data Structures"),
    ("2401.00004", "Robust Selectors under Page Redesigns", "Donald Knuth", "Software Engineering"),
    ("2401.00005", "Scheduling Polite Crawls at Scale", "Leslie Lamport, Tim Berners-Lee", "Networking"),
]


def definition_list_page() -> str:
    """One record split over two neighbours: the id in a ``dt``, the rest in the ``dd`` after it."""
    entries = "".join(
        f"""<dt><a href="/abs/{number}" title="Abstract">arXiv:{number}</a></dt>
            <dd><div class="meta"><div class="list-title">{title}</div>
                <div class="list-authors">{authors}</div>
                <div class="list-subjects">{subject}</div></div></dd>"""
        for number, title, authors, subject in PAPERS
    )
    return f"<html><body><main><dl id='articles'>{entries}</dl></main></body></html>"


STORIES = [
    ("Show HN: A tiny scraper that needs no model", "example.com", 412, "pg", 96),
    ("Why tables are still the best layout for data", "tables.dev", 87, "dang", 14),
    ("The slow death of the next-page link", "weblog.io", 230, "sama", 58),
    ("Notes on reading HTML with no classes", "plainhtml.org", 55, "tptacek", 7),
    ("An old browser trick that still works", "tricks.net", 301, "patio11", 120),
]


def title_and_details_rows_page() -> str:
    """A title row, a details row, then an empty spacer row, repeated."""
    rows = "".join(
        f"""<tr class="athing" id="{n}"><td class="rank">{n}.</td>
              <td class="title"><span class="titleline"><a href="https://{site}/post/{n}">{title}</a>
                <span class="sitebit">(<span class="sitestr">{site}</span>)</span></span></td></tr>
            <tr><td></td><td class="subtext"><span class="score">{points} points</span> by
                <a class="hnuser" href="user?id={user}">{user}</a>
                <a class="discuss" href="item?id={n}">{comments} comments</a></td></tr>
            <tr class="spacer" style="height:5px"></tr>"""
        for n, (title, site, points, user, comments) in enumerate(STORIES, 1)
    )
    return f"<html><body><table id='hnmain'><tr><td><table>{rows}</table></td></tr></table></body></html>"


def headed_table_page() -> str:
    """A table with no classes at all: the heading row is the only source of column names."""
    countries = [("India", "1,417,492,000", "17.3%", "Asia"), ("China", "1,408,280,000", "17.2%", "Asia"),
                 ("United States", "340,110,988", "4.2%", "Americas"), ("Indonesia", "282,477,584", "3.5%", "Asia"),
                 ("Pakistan", "241,499,431", "2.9%", "Asia")]
    rows = "".join(
        f'<tr><td><a href="/wiki/{name.replace(" ", "_")}">{name}</a></td><td>{people}</td><td>{share}</td><td>{region}</td></tr>'
        for name, people, share, region in countries
    )
    return f"""<html><body><div id="content"><table class="wikitable">
               <tr><th>Location</th><th>Population</th><th>% of world</th><th>Region</th></tr>
               {rows}</table></div></body></html>"""


def several_links_page() -> str:
    """A title link, an author link and a comments link in every card."""
    cards = "".join(
        f"""<div class="story"><a class="headline" href="/s/{n}">Story headline number {n} is here</a>
              <div class="byline"><a class="author" href="/u/user{n}">user{n}</a>
              <a class="comments" href="/s/{n}/comments">{n * 3} comments</a></div></div>"""
        for n in range(1, 7)
    )
    return f"<html><body><main>{cards}</main></body></html>"


def card_with_stats_line_page() -> str:
    """The card is the record. Its stats line repeats just as often but holds only part of it."""
    cards = "".join(
        f"""<article class="repo"><h2><a href="/org{n}/project{n}">org{n} / project{n}</a></h2>
              <p class="about">Project {n} does something useful for people who need thing {n}.</p>
              <div class="stats"><span class="language">Language{n % 3}</span>
                <a class="stars" href="/org{n}/project{n}/stargazers">{n * 1234} stars</a>
                <a class="forks" href="/org{n}/project{n}/forks">{n * 87} forks</a>
                <span class="today">{n * 12} stars today</span></div></article>"""
        for n in range(1, 8)
    )
    return f"<html><body><main>{cards}</main></body></html>"


def list_marked_as_menu_page() -> str:
    """Posts in ``<ul class="menu">`` inside the main landmark, next to a real navigation menu."""
    nav = "".join(f'<li><a href="/section/{n}">Section number {n} of the site</a></li>' for n in range(12))
    posts = "".join(
        f"""<li><h3 class="event-title"><a href="/blog/post-{n}">Blog post number {n} has a long title</a></h3>
              <p class="summary">Summary of post {n}, long enough to read as a sentence.</p>
              <time datetime="2026-09-{n:02d}">Sep {n}</time></li>"""
        for n in range(1, 9)
    )
    return f"""<html><body><nav><ul class="menu">{nav}</ul></nav>
               <section role="main"><ul class="list-recent-posts menu">{posts}</ul></section></body></html>"""


def neighbouring_cards_page() -> str:
    """Odd and even cards carry different classes. Each is its own record, not half of a pair."""
    cards = "".join(
        f"""<div class="{'odd' if n % 2 else 'even'}"><span class="product">Product number {n}</span>
              <span class="cost">${n}9.50</span><span class="maker">Maker {n}</span></div>"""
        for n in range(1, 11)
    )
    return f"<html><body><main><div id='results'>{cards}</div></main></body></html>"


def few_sections_and_a_list_page() -> str:
    """Four large page sections with plenty of text, and a longer list of plain records."""
    sections = "".join(
        f"""<section class="feature"><h2>Feature section number {n}</h2>
              <p class="lead">{'A long paragraph about this part of the site. ' * 6}</p>
              <p class="more">{'More words in a second paragraph. ' * 6}</p>
              <span class="tagline">Tagline {n}</span><span class="kicker">Kicker {n}</span></section>"""
        for n in range(1, 5)
    )
    rows = "".join(
        f'<li class="entry"><span class="what">Entry number {n}</span><span class="who">Person {n}</span>'
        f'<span class="place">Town {n}</span></li>'
        for n in range(1, 21)
    )
    return f"<html><body><main>{sections}<ul id='entries'>{rows}</ul></main></body></html>"


def mixed_class_siblings_page() -> str:
    """Rows of one list with different classes each: no single class selects them all."""
    kinds = ["promoted wide", "plain", "plain recent", "sponsored", "plain", "wide recent", "plain", "archived"]
    rows = "".join(
        f"""<li class="{kind}"><span class="job">Job opening number {n}</span>
              <span class="firm">Firm {n}</span><span class="pay">${n}5,000</span></li>"""
        for n, kind in enumerate(kinds, 1)
    )
    return f"<html><body><main><ul id='openings'>{rows}</ul></main></body></html>"


def test_record_split_over_dt_and_dd_is_read_as_one_row():
    result = build_recipe(definition_list_page(), "https://papers.test/list")
    assert result.recipe.container == "#articles > dt"
    fields = {f.name: f.select for f in result.recipe.fields}
    # "+" reads from the element right after the item: the dd that follows each dt.
    assert fields == {
        "title": ["+ div.list-title"],
        "text": ["a"],
        "authors": ["+ div.list-authors"],
        "subjects": ["+ div.list-subjects"],
        "url": ["a@href"],
    }
    assert len(result.records) == len(PAPERS)
    assert result.records[2] == {
        "title": "Fast Tree Matching for Document Layouts",
        "text": "arXiv:2401.00003",
        "authors": "Edsger Dijkstra, Barbara Liskov",
        "subjects": "Data Structures",
        "url": "https://papers.test/abs/2401.00003",
    }


def test_a_class_that_says_title_beats_link_text():
    """The link holds the paper's number. The title is the div whose class says so."""
    result = build_recipe(definition_list_page(), "https://papers.test/list")
    assert result.records[0]["title"] == PAPERS[0][1]


def test_title_row_and_details_row_make_one_record():
    result = build_recipe(title_and_details_rows_page(), "https://news.test/")
    # The row with the title is the item; the spacer rows and the details rows are not.
    assert result.recipe.container == "tr.athing"
    assert len(result.records) == len(STORIES)
    first = result.records[0]
    assert first["title"] == "Show HN: A tiny scraper that needs no model"
    assert first["url"] == "https://example.com/post/1"
    assert first["sitestr"] == "example.com"
    # These come from the row after it.
    assert first["hnuser"] == "pg"
    assert first["discuss"] == "96 comments"
    assert first["hnuser_url"] == "https://news.test/user?id=pg"
    assert result.records[4]["hnuser"] == "patio11"


def test_plain_table_takes_its_column_names_from_the_heading_row():
    result = build_recipe(headed_table_page(), "https://wiki.test/")
    assert result.recipe.container == "table.wikitable > tr"
    # The heading row is one of the rows but holds no data: it must not become a record,
    # and it must not make the cells look like an optional extra.
    assert len(result.records) == 5
    assert [f.name for f in result.recipe.fields] == ["location", "population", "of_world", "region", "location_url"]
    assert result.records[2] == {
        "location": "United States",
        "population": 340110988,
        "of_world": "4.2%",
        "region": "Americas",
        "location_url": "https://wiki.test/wiki/United_States",
    }


def test_each_link_is_named_after_the_text_it_belongs_to():
    result = build_recipe(several_links_page(), "https://x.test/")
    assert [f.name for f in result.recipe.fields] == [
        "title", "author", "comments", "url", "author_url", "comments_url",
    ]
    assert result.records[0]["url"] == "https://x.test/s/1"
    assert result.records[0]["author_url"] == "https://x.test/u/user1"
    assert result.records[0]["comments_url"] == "https://x.test/s/1/comments"


def test_the_whole_card_is_the_record_not_its_stats_line():
    result = build_recipe(card_with_stats_line_page(), "https://code.test/")
    assert result.recipe.container == "article.repo"
    names = [f.name for f in result.recipe.fields]
    # The title and description live outside the stats line; the stats live inside it.
    assert names[:6] == ["title", "about", "language", "stars", "forks", "today"]
    assert result.records[1]["title"] == "org2 / project2"
    assert result.records[1]["stars"] == "2468 stars"


def test_list_in_main_content_wins_even_when_its_class_says_menu():
    result = build_recipe(list_marked_as_menu_page(), "https://blog.test/")
    assert result.recipe.container == "ul.list-recent-posts.menu > li"
    assert len(result.records) == 8
    assert result.records[0] == {
        "title": "Blog post number 1 has a long title",
        "summary": "Summary of post 1, long enough to read as a sentence.",
        "date": "2026-09-01",
        "url": "https://blog.test/blog/post-1",
    }


def test_neighbouring_cards_are_separate_records_not_a_pair():
    result = build_recipe(neighbouring_cards_page(), "https://x.test/")
    assert result.recipe.container == "#results > div"
    assert len(result.records) == 10
    assert not any(spec.startswith("+") for f in result.recipe.fields for spec in f.select)
    assert result.records[1] == {"product": "Product number 2", "price": "$29.50", "maker": "Maker 2"}


def test_a_long_list_beats_a_few_large_sections():
    result = build_recipe(few_sections_and_a_list_page(), "https://x.test/")
    assert result.recipe.container == "li.entry"
    assert len(result.records) == 20


def test_a_list_of_only_four_is_still_found_when_nothing_larger_competes():
    cards = "".join(
        f'<div class="plan"><h3>Plan number {n}</h3><span class="cost">${n}9.00</span>'
        f'<p class="blurb">What plan {n} gives you each month.</p></div>'
        for n in range(1, 5)
    )
    result = build_recipe(f"<html><body><main>{cards}</main></body></html>", "https://x.test/pricing")
    assert result.recipe.container == "div.plan"
    assert len(result.records) == 4


def test_rows_with_different_classes_are_found_through_their_parent():
    result = build_recipe(mixed_class_siblings_page(), "https://jobs.test/")
    assert result.recipe.container == "#openings > li"
    assert len(result.records) == 8
    assert result.records[3] == {"job": "Job opening number 4", "firm": "Firm 4", "price": "$45,000"}
