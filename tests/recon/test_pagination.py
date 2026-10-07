import pytest
from bs4 import BeautifulSoup

from scrapewizard.recon.pagination import PaginationDetector, find_next_url

URL = "https://example.com/list"


def detect(html: str, url: str = URL):
    soup = BeautifulSoup(html, "lxml")
    return soup, PaginationDetector(soup, url).detect()


def assert_selector_valid(soup, result):
    """Any selector returned must be valid CSS that matches exactly one element."""
    assert result["selector"] is not None
    assert len(soup.select(result["selector"])) == 1


def test_plain_next_link_gives_url_without_invalid_selector():
    soup, result = detect("<a href='/p2'>Next</a>")
    assert result["type"] == "next_button"
    assert result["next_url"] == "https://example.com/p2"
    # No class or id to anchor on: no selector rather than an invalid one.
    assert result["selector"] is None


def test_next_inside_classed_wrapper():
    soup, result = detect("<ul class='pager'><li class='next'><a href='page-2.html'>next</a></li></ul>")
    assert result["type"] == "next_button"
    assert result["selector"] == "li.next > a"
    assert_selector_valid(soup, result)


def test_class_needing_escape_is_not_used_in_selector():
    soup, result = detect("<a class='md:flex next-link' href='/p2'>Next</a>")
    assert result["type"] == "next_button"
    assert ":" not in (result["selector"] or "").replace(":scope", "")
    assert_selector_valid(soup, result)


def test_rel_next_icon_only_link():
    soup, result = detect("<a rel='next' href='/p2'><svg></svg></a>")
    assert result["type"] == "next_button"
    assert result["next_url"] == "https://example.com/p2"
    assert_selector_valid(soup, result)


def test_numbered_pages_with_current_marker():
    html = """<div class='pagination'>
        <a href='?page=1'>1</a><span class='current'>2</span>
        <a href='?page=3'>3</a><a href='?page=4'>4</a></div>"""
    soup, result = detect(html, "https://example.com/list?page=2")
    assert result["type"] == "numbered"
    assert result["next_url"] == "https://example.com/list?page=3"


def test_load_more_button():
    soup, result = detect("<button id='more'>Load more</button>")
    assert result["type"] == "load_more"
    assert result["selector"] == "#more"


def test_previous_link_in_prev_next_wrapper_is_not_next():
    html = "<div class='prev-next'><a href='/p1'>Previous</a><a href='/p3'>Next</a></div>"
    assert find_next_url(BeautifulSoup(html, "lxml"), "https://example.com/p2") == "https://example.com/p3"


def test_no_pagination():
    _, result = detect("<p>Nothing here</p><a href='/about'>About</a>")
    assert result == {"detected": False, "type": "none"}


def test_find_next_url_ignores_anchor_and_script_links():
    html = "<a href='#'>Next</a><a href='javascript:void(0)'>Next</a>"
    assert find_next_url(BeautifulSoup(html, "lxml"), URL) is None
