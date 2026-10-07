"""Getting a page: plain HTTP first, a real browser only when needed."""
import re

import httpx

from scrapewizard.core.logging import log

# Sent with plain HTTP requests so servers answer as they would for a person.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


META_CHARSET_RE = re.compile(rb"<meta[^>]+charset\s*=\s*[\"']?\s*([\w-]+)", re.I)


class FetchError(Exception):
    """A page could not be retrieved. The message is safe to show to the user."""


def decode_body(response: httpx.Response) -> str:
    """Decode a response body, honouring the page's own <meta charset>.

    When the server names no charset, httpx assumes UTF-8, which garbles pages
    written in another encoding. The declaration inside the HTML is used instead.
    """
    if response.charset_encoding:
        return response.text
    declared = META_CHARSET_RE.search(response.content[:4096])
    encoding = declared.group(1).decode("ascii", "ignore") if declared else "utf-8"
    try:
        return response.content.decode(encoding, errors="replace")
    except LookupError:
        return response.content.decode("utf-8", errors="replace")


def fetch_http(url: str, timeout: float = 20.0) -> str:
    """Fetch a page with one HTTP request. No JavaScript is run."""
    try:
        response = httpx.get(url, headers=BROWSER_HEADERS, timeout=timeout, follow_redirects=True)
    except httpx.TimeoutException as e:
        raise FetchError(f"The site did not answer within {int(timeout)} seconds.") from e
    except httpx.HTTPError as e:
        raise FetchError(f"Could not connect to the site ({type(e).__name__}).") from e
    if response.status_code in (401, 403, 429):
        raise FetchError(f"The site refused the request (HTTP {response.status_code}). It may block automated access.")
    if response.status_code >= 400:
        raise FetchError(f"The site answered with an error (HTTP {response.status_code}).")
    return decode_body(response)


def fetch_browser(url: str, timeout: float = 30.0) -> str:
    """Load a page in headless Chromium and return the HTML after scripts have run."""
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError as e:
        raise FetchError("This page needs a browser. Install it with: pip install playwright") from e

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=BROWSER_HEADERS["User-Agent"])
                page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                try:
                    # Let late requests finish, but don't fail on pages that never go quiet.
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PlaywrightError:
                    log(f"Page did not reach network idle: {url}", level="debug")
                return page.content()
            finally:
                browser.close()
    except PlaywrightError as e:
        message = str(e)
        if "Executable doesn't exist" in message or "playwright install" in message:
            raise FetchError("The browser is not installed. Run: playwright install chromium") from e
        raise FetchError(f"The browser could not load the page ({message.splitlines()[0][:120]}).") from e


def fetch(url: str, mode: str = "http") -> str:
    """Fetch a page using the given mode: 'http' or 'browser'."""
    return fetch_browser(url) if mode == "browser" else fetch_http(url)
