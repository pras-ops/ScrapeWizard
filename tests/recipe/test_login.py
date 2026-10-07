"""Sites that only show their data when signed in."""
import csv
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from typer.testing import CliRunner

from scrapewizard.cli.commands.recipe import _build_signed_in
from scrapewizard.cli.main import app
from scrapewizard.recipe.fetch import fetch_http, sign_in
from scrapewizard.recipe.model import load_recipe, save_recipe
from scrapewizard.recipe.state import save_session, save_state, session_path

runner = CliRunner()

MEMBERS = "".join(
    f'<div class="order"><h3>Order number {n}</h3><span class="total">${n}5.00</span></div>'
    for n in range(1, 6)
)
LOGIN_FORM = """<html><body><h1>Sign in</h1>
<form method="post" action="/login"><input name="user"><input name="pass" type="password">
<button type="submit">Sign in</button></form></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body="", headers=()):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        signed_in = "session=ok" in (self.headers.get("Cookie") or "")
        if self.path == "/orders":
            if signed_in:
                self._send(200, f"<html><body><main>{MEMBERS}</main></body></html>")
            else:
                self._send(302, headers=[("Location", "/login")])
        elif self.path == "/login":
            self._send(200, LOGIN_FORM)
        else:
            self._send(404, "not found")

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self._send(302, headers=[("Location", "/orders"), ("Set-Cookie", "session=ok; Path=/")])

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


def a_person_signs_in(page):
    """Stands in for the user typing into the visible browser window."""
    page.fill("input[name=user]", "someone")
    page.fill("input[name=pass]", "a-password")
    page.click("button[type=submit]")
    page.wait_for_url("**/orders")


def test_without_signing_in_the_list_is_not_visible(site):
    assert "Order number 1" not in fetch_http(site + "/orders")


def test_sign_in_captures_the_session_and_the_page_the_user_ends_on(site):
    storage, landed, html = sign_in(site + "/orders", a_person_signs_in, headless=True)
    assert landed == site + "/orders"
    assert "Order number 1" in html
    assert any(c["name"] == "session" and c["value"] == "ok" for c in storage["cookies"])


def test_building_after_sign_in_marks_the_recipe_as_needing_one(site):
    result, storage = _build_signed_in(site + "/orders", [], wait=a_person_signs_in, headless=True)
    assert result.recipe.login is True
    assert result.recipe.fetch == "browser"
    assert result.recipe.url == site + "/orders"      # where the user ended up, not where they started
    assert len(result.records) == 5
    assert storage["cookies"]


def saved_recipe(site, folder):
    result, storage = _build_signed_in(site + "/orders", [], wait=a_person_signs_in, headless=True)
    path = save_recipe(result.recipe, folder / "orders.recipe.yaml")
    save_state(path, result.recipe, result.records, 1)
    save_session(path, storage)
    return path


def test_a_saved_sign_in_is_reused_on_later_runs(site, folder):
    path = saved_recipe(site, folder)
    assert load_recipe(path).login is True
    assert "password" not in path.read_text(encoding="utf-8")      # the recipe holds no credentials

    result = runner.invoke(app, ["run", "orders.recipe.yaml"])

    assert result.exit_code == 0, result.output
    assert "5 rows from 1 page" in result.output
    with open(folder / "orders.csv", encoding="utf-8", newline="") as f:
        assert [r["title"] for r in csv.DictReader(f)] == [f"Order number {n}" for n in range(1, 6)]


def test_the_sign_in_folder_ignores_itself_in_git(site, folder):
    path = saved_recipe(site, folder)
    assert session_path(path).parent.name == ".scrapewizard"
    assert (folder / ".scrapewizard" / ".gitignore").read_text(encoding="utf-8").splitlines()[-1] == "*"


def test_a_missing_sign_in_says_how_to_make_one(site, folder):
    path = saved_recipe(site, folder)
    session_path(path).unlink()

    result = runner.invoke(app, ["run", "orders.recipe.yaml"])

    assert result.exit_code == 1
    assert "This recipe needs a sign-in, and none is saved beside it." in result.output
    assert "--login --out orders" in result.output


def test_an_expired_sign_in_is_named_as_the_likely_cause(site, folder):
    path = saved_recipe(site, folder)
    session_path(path).write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

    result = runner.invoke(app, ["run", "orders.recipe.yaml"])

    assert result.exit_code == 1
    assert "The saved sign-in has probably expired." in result.output
    assert "could not be repaired" not in result.output
