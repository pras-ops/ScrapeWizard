class ConsoleNetworkTracker:
    """
    Captures console errors and network response failures (4xx/5xx status codes)
    on a Playwright page during a test execution block.
    """
    def __init__(self, page):
        self.page = page
        self.console_errors = []
        self.network_errors = []
        self._setup_listeners()

    def _setup_listeners(self):
        def handle_console(msg):
            if msg.type == "error":
                location = msg.location or {}
                url = location.get("url") or "unknown"
                line = location.get("lineNumber") or 0
                self.console_errors.append(f"[{url}:{line}] {msg.text}")
        
        def handle_response(response):
            if response.status >= 400:
                self.network_errors.append(f"[{response.status}] {response.url}")

        self.page.on("console", handle_console)
        self.page.on("response", handle_response)

    def flush(self):
        """Return the collected errors and clear the tracking buffers."""
        console = list(self.console_errors)
        network = list(self.network_errors)
        self.console_errors.clear()
        self.network_errors.clear()
        return console, network
