"""Getting a page: plain HTTP first, a real browser only when needed."""
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

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


# New elements a page must gain before "load more" or scrolling counts as having loaded content.
MIN_GROWTH = 5
META_CHARSET_RE = re.compile(rb"<meta[^>]+charset\s*=\s*[\"']?\s*([\w-]+)", re.I)


class FetchError(Exception):
    """A page could not be retrieved. The message is safe to show to the user.

    ``browser_may_help`` is True when the site answered but refused a plain
    request, which a real browser sometimes gets past. It is False when the
    site could not be reached at all.
    """

    def __init__(self, message: str, browser_may_help: bool = False):
        super().__init__(message)
        self.browser_may_help = browser_may_help


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


_client: Optional[httpx.Client] = None


def _http_client() -> httpx.Client:
    """One client for the whole process, so connections to a site are reused.

    Opening a new connection for every page costs a TLS handshake each time,
    which dominates when hundreds of item pages are read. The client is safe
    to share between threads.
    """
    global _client
    if _client is None:
        _client = httpx.Client(headers=BROWSER_HEADERS, follow_redirects=True)
    return _client


def fetch_http(url: str, timeout: float = 20.0) -> str:
    """Fetch a page with one HTTP request. No JavaScript is run."""
    try:
        response = _http_client().get(url, timeout=timeout)
    except httpx.TimeoutException as e:
        raise FetchError(f"The site did not answer within {int(timeout)} seconds.") from e
    except httpx.HTTPError as e:
        raise FetchError(f"Could not connect to the site ({type(e).__name__}).") from e
    if response.status_code in (401, 403, 429):
        raise FetchError(
            f"The site refused the request (HTTP {response.status_code}). It may block automated access.",
            browser_may_help=True,
        )
    if response.status_code >= 400:
        raise FetchError(f"The site answered with an error (HTTP {response.status_code}).")
    return decode_body(response)


class BrowserSession:
    """One headless browser kept open for a whole run.

    Used when pages need JavaScript, and to follow lists that grow in place
    (a "load more" button or infinite scroll) instead of moving to a new address.
    """

    def __init__(self, timeout: float = 30.0, storage_state: Any = None, headless: bool = True):
        """
        Args:
            storage_state: A saved sign-in (cookies and local storage), as a
                file path or the dict Playwright produces. None for a clean browser.
            headless: False shows the window, for signing in by hand.
        """
        self.timeout = timeout
        self.storage_state = storage_state
        self.headless = headless
        self._playwright = None
        self._browser = None
        self.context = None
        self.page = None

    def __enter__(self) -> "BrowserSession":
        try:
            from playwright.sync_api import Error as PlaywrightError, sync_playwright
        except ImportError as e:
            raise FetchError("This page needs a browser. Install it with: pip install playwright") from e
        self._error = PlaywrightError
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self.context = self._browser.new_context(
                user_agent=BROWSER_HEADERS["User-Agent"],
                storage_state=str(self.storage_state) if isinstance(self.storage_state, Path) else self.storage_state,
            )
            self.page = self.context.new_page()
        except PlaywrightError as e:
            self.__exit__(None, None, None)
            raise self._as_fetch_error(e) from e
        return self

    def __exit__(self, *exc) -> None:
        for closer in (getattr(self._browser, "close", None), getattr(self._playwright, "stop", None)):
            if closer:
                try:
                    closer()
                except Exception:
                    pass  # the browser may already be gone; there is nothing left to release
        self._browser = self._playwright = self.context = self.page = None

    @staticmethod
    def _as_fetch_error(error: Exception) -> FetchError:
        message = str(error)
        if "Executable doesn't exist" in message or "playwright install" in message:
            return FetchError("The browser is not installed. Run: playwright install chromium")
        return FetchError(f"The browser could not load the page ({message.splitlines()[0][:120]}).")

    def _settle(self) -> None:
        try:
            # Let late requests finish, but do not fail on pages that never go quiet.
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except self._error:
            log("Page did not reach network idle", level="debug")

    def open(self, url: str) -> str:
        """Go to a page and return its HTML after scripts have run."""
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
        except self._error as e:
            raise self._as_fetch_error(e) from e
        self._settle()
        return self.page.content()

    def _element_count(self) -> int:
        return self.page.evaluate("document.getElementsByTagName('*').length")

    def _wait_for_growth(self, before: int, timeout: float = 8.0, quiet: float = 0.6) -> bool:
        """Wait until the page has gained real content and then stopped changing.

        A spinner appearing is not content, so a handful of new elements does
        not count. "Network idle" cannot be used here: Playwright reaches that
        state once per page load and reports it as reached ever after.
        """
        deadline = time.monotonic() + timeout
        last = before
        last_change = time.monotonic()
        while time.monotonic() < deadline:
            self.page.wait_for_timeout(150)
            now = self._element_count()
            if now != last:
                last, last_change = now, time.monotonic()
            elif now >= before + MIN_GROWTH and time.monotonic() - last_change >= quiet:
                return True
        return last >= before + MIN_GROWTH

    def click_more(self, selector: str) -> Optional[str]:
        """Click a "load more" control. Returns the grown page, or None if nothing more loaded."""
        try:
            button = self.page.locator(selector).first
            if button.count() == 0 or not button.is_visible() or not button.is_enabled():
                return None
            before = self._element_count()
            button.click(timeout=5000)
            if not self._wait_for_growth(before):
                return None
            return self.page.content()
        except self._error:
            return None

    def scroll_more(self) -> Optional[str]:
        """Scroll to the bottom. Returns the grown page, or None if the page did not grow."""
        try:
            before = self._element_count()
            self.page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            if not self._wait_for_growth(before):
                return None
            return self.page.content()
        except self._error:
            return None


def sign_in(url: str, wait: Callable[[Any], None], headless: bool = False,
            timeout: float = 30.0) -> Tuple[Dict[str, Any], str, str]:
    """Open a page for the user to sign in, and capture the session when they are done.

    Args:
        wait: Called with the browser page; returns when the user has signed
            in and is on the page they want. By default this waits for Enter.
        headless: Only tests hide the window.

    Returns:
        (the saved sign-in, the address the user ended on, that page's HTML)
    """
    with BrowserSession(timeout, headless=headless) as session:
        session.open(url)
        wait(session.page)
        try:
            session.page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
            return session.context.storage_state(), session.page.url, session.page.content()
        except session._error as e:
            raise FetchError("The browser window was closed before the sign-in could be saved.") from e


def fetch_browser(url: str, timeout: float = 30.0) -> str:
    """Load a page in headless Chromium and return the HTML after scripts have run."""
    with BrowserSession(timeout) as session:
        return session.open(url)


def fetch(url: str, mode: str = "http") -> str:
    """Fetch a page using the given mode: 'http' or 'browser'."""
    return fetch_browser(url) if mode == "browser" else fetch_http(url)
