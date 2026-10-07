"""Lists that grow in place (a "load more" button, infinite scroll), followed in a real browser."""
import csv
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from typer.testing import CliRunner

from scrapewizard.cli.main import app
from scrapewizard.recipe.model import load_recipe

runner = CliRunner()

CARD = ('<div class="product"><h2><a href="/item/{n}">Product number {n}</a></h2>'
        '<span class="cost">${n}.99</span></div>')
FIRST_FIVE = "".join(CARD.format(n=n) for n in range(1, 6))

# Adds five more cards, up to fifteen, after a short delay like a real request.
APPEND_JS = """
let n = 5, busy = false;
function addFive(done) {
  busy = true;
  document.body.insertAdjacentHTML('beforeend', '<p id="spinner">Loading...</p>');
  setTimeout(() => {
    document.getElementById('spinner').remove();
    const list = document.getElementById('list');
    for (let i = 0; i < 5; i++) {
      n++;
      list.insertAdjacentHTML('beforeend',
        `<div class="product"><h2><a href="/item/${n}">Product number ${n}</a></h2>` +
        `<span class="cost">$${n}.99</span></div>`);
    }
    busy = false;
    if (done) done();
  }, 300);
}
"""

LOAD_MORE_PAGE = f"""<html><body><main id="list">{FIRST_FIVE}</main>
<button id="more">Load more</button>
<script>{APPEND_JS}
document.getElementById('more').addEventListener('click', () => {{
  if (!busy) addFive(() => {{ if (n >= 15) document.getElementById('more').style.display = 'none'; }});
}});
</script></body></html>"""

SCROLL_PAGE = f"""<html><head><style>.product {{ height: 320px; }}</style></head>
<body><main id="list">{FIRST_FIVE}</main>
<script>{APPEND_JS}
window.addEventListener('scroll', () => {{
  const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 5;
  if (atBottom && !busy && n < 15) addFive();
}});
</script></body></html>"""

PAGES = {"/more": LOAD_MORE_PAGE, "/scroll": SCROLL_PAGE, "/plain": f"<html><body><main>{FIRST_FIVE}</main></body></html>"}


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
def folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def titles(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [row["title"] for row in csv.DictReader(f)]


def test_load_more_button_is_followed_to_the_end(site, folder):
    result = runner.invoke(app, [site + "/more", "--all-pages", "--out", "shop"])

    assert result.exit_code == 0, result.output
    assert "This list loads more as you go." in result.output
    assert "Following it needs a browser." in result.output
    assert titles(folder / "shop.csv") == [f"Product number {n}" for n in range(1, 16)]

    recipe = load_recipe(folder / "shop.recipe.yaml")
    assert recipe.pagination["type"] == "load_more"
    assert recipe.pagination["select"] == "#more"
    assert recipe.fetch == "browser"


def test_load_more_respects_a_page_limit(site, folder):
    result = runner.invoke(app, [site + "/more", "--pages", "2", "--out", "shop"])
    assert result.exit_code == 0, result.output
    assert len(titles(folder / "shop.csv")) == 10


def test_infinite_scroll_is_found_when_more_pages_are_asked_for(site, folder):
    """The first batch is in the plain page, so only a browser can tell that it scrolls."""
    result = runner.invoke(app, [site + "/scroll", "--all-pages", "--out", "shop"])

    assert result.exit_code == 0, result.output
    assert "Checking in a browser whether it loads more" in result.output
    assert titles(folder / "shop.csv") == [f"Product number {n}" for n in range(1, 16)]
    assert load_recipe(folder / "shop.recipe.yaml").pagination["type"] == "scroll"


def test_a_saved_scrolling_recipe_runs_again(site, folder):
    runner.invoke(app, [site + "/scroll", "--all-pages", "--out", "shop"])
    (folder / "shop.csv").unlink()

    result = runner.invoke(app, ["run", "shop.recipe.yaml"])

    assert result.exit_code == 0, result.output
    assert "15 rows from 3 pages   0 new, 0 changed, 0 removed since last run" in result.output
    assert len(titles(folder / "shop.csv")) == 15


def test_a_plain_single_page_is_reported_as_the_whole_list(site, folder):
    result = runner.invoke(app, [site + "/plain", "--all-pages", "--out", "shop"])

    assert result.exit_code == 0, result.output
    assert "It doesn't: this is the whole list." in result.output
    assert len(titles(folder / "shop.csv")) == 5
    assert load_recipe(folder / "shop.recipe.yaml").fetch == "http"
