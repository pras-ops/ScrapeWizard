# 🕷️ ScrapeWizard — Scraper Research & Improvement Plan

> Research date: 2026-10-07. Sources: GitHub projects, Hacker News threads, tool docs and
> independent reviews (listed at the end). **Reddit blocks automated access**, so r/webscraping
> could not be read directly; Hacker News and practitioner write-ups stand in for it.
> Every claim about ScrapeWizard's own code was checked against this branch.

---

## 1. Where ScrapeWizard stands today (measured)

| Area | Finding |
|---|---|
| **AI dependency** | `build` cannot run without an LLM. It makes 2 calls minimum (understand the page, write the scraper) and more on repair |
| **What the AI produces** | A whole Python file. Free-form code is hard to validate, diff or repair |
| **Self-healing** | **Not used by the scraper.** `engine/selector_engine.py`, `fingerprint.py` and `healing.py` are called only by their own tests. Generated scrapers have plain selectors |
| **Speed** | About **18 seconds of `time.sleep` per build** purely to animate progress bars (`_progress_step` in `core/orchestrator.py`) |
| **Browser launches** | At least 4 per build: a **headed** probe window, recon, a test run and the final run |
| **Fetching** | Browser only. No plain-HTTP path, even for static pages |
| **Data sources** | HTML only. The `Scanner` already detects backend API calls and JSON responses, but nothing uses them for extraction |
| **Dependencies** | 24 runtime packages, including `pytest`, `pytest-asyncio`, `pytest-mock`, `pandas`, `openpyxl`, `fastapi`, `uvicorn`, two LLM SDKs, two HTTP clients and two prompt libraries |
| **Tests** | 50 pass, 1 pre-existing failure (`test_detect_hardware_balanced`) |

So the scraper is currently heavy, slow to build and AI-bound, and its best idea (self-healing)
isn't connected.

---

## 2. The landscape

| Tool | Stars (approx.) | What it is | What to learn from it |
|---|---|---|---|
| **Scrapy** | 59–62k | Mature Python crawl framework: scheduler, pipelines, middleware | Don't rebuild this. Export to it if users need scale |
| **Crawlee** (JS + Python) | 20–26k | Queues, retries, sessions, proxies, one interface for HTTP and browser | The HTTP-first, browser-fallback idea |
| **Crawl4AI** | 58–82k | Pages → clean Markdown / structured data for LLM use | **`generate_schema`: the LLM writes a CSS/XPath schema once, then extraction runs with no LLM** |
| **Firecrawl** | 70k+ | URL → Markdown/JSON API, self-hostable | "One call, clean output" simplicity |
| **ScrapeGraphAI** | ~20k | Natural-language prompt → data, LLM on each run | The per-page LLM cost model people complain about |
| **Scrapling** | ~69k | Python library with **adaptive selectors**: saves an element's profile, relocates it after a redesign; stealth fetchers | **Your closest competitor on self-healing** (see §3) |
| **Maxun** | ~13k | No-code platform: record actions into a reusable "robot", scheduling, sites → APIs/sheets | Recorder UX; but it's a full Node platform, not a light CLI |
| **AutoScraper** | small, older | Give sample values, it learns the rules; save/load the model | "Learn from an example" with zero selectors |
| **LLM Scraper** | — | Schema + LLM + Playwright | HN feedback: generate selectors once instead |

Supporting layers worth using rather than writing:

| Need | Options | Note |
|---|---|---|
| Fast HTML parsing | **selectolax**, lxml | selectolax is ~10–15x faster than BeautifulSoup on parse-and-extract; lxml is already a dependency |
| Looking like a real browser over HTTP | **curl_cffi** (`impersonate="chrome"`) | In one 2026 benchmark a 21-line wrapper matched a heavily patched Chromium fork on TLS-fingerprint targets |
| Stealth browser | **patchright** (drop-in for Playwright), nodriver (AGPL licence), camoufox (slow, strongest on fingerprinting) | Patchright is the lowest-effort upgrade for existing Playwright code |
| Data hidden in the page | JSON-LD, `__NEXT_DATA__`, hydration payloads | Often the whole dataset, already structured, with no selectors to break |

---

## 3. What the pasted comparison got right and wrong

**Right:**
- AI should be a fallback, not the per-page engine.
- Extraction schemas, repeated-structure detection, network/API discovery, pagination
  intelligence, data-quality scoring and change detection are the right feature set.
- Don't try to out-Scrapy Scrapy.

**Wrong or missing:**
- It rates ScrapeWizard's self-healing 5/5. **The scraper doesn't use it at all** (§1).
- It never mentions **Scrapling**, which already ships adaptive selectors to a very large
  audience, or **Maxun**, which already does record-to-robot.
- Its roadmap (crawl engine, URL queue, job queue with Redis/Celery, proxy management, Kafka
  and Postgres destinations, cloud workers, billing) is the opposite of "lightweight and simple."
  That is rebuilding Crawlee and Apify.
- The star ratings are opinion, not measurement.

**The real gap in Scrapling:** an independent test found its adaptive matching tracks
**individual elements**. In a three-element test it recovered one. It's also a library you write
code against. Nothing in it builds the scraper for you or checks that the healed result is
correct.

---

## 4. What developers actually complain about

From Hacker News threads on LLM scraping and 2026 industry write-ups:

1. **LLM-per-page is too expensive and slow.** "Scary OpenAI bills"; one to two orders of
   magnitude dearer than normal extraction. The repeated advice: have the LLM produce
   **selectors or a schema once**, then reuse them.
2. **Feeding raw HTML to an LLM wastes tokens and hurts accuracy.** Strip or simplify first.
3. **Anti-bot is the real bottleneck**, not parsing.
4. **Silent data decay.** Scrapers "succeed and still give you the wrong data": 200 responses,
   fields drifting, nobody notices for weeks.
5. **Maintenance treadmill.** Each patch works briefly, then decays.
6. **Hallucination worry** with LLM extraction on data that has to be right.

---

## 5. The niche to own

> **Point it at a page. Get a small, readable scraper recipe. It runs fast with no AI. When the
> site changes, it notices, repairs itself, and proves the repair with data checks.**

Why this is different from each neighbour:

| Versus | Difference |
|---|---|
| Scrapling | It heals single elements inside code you wrote. ScrapeWizard **builds** the scraper and heals **whole collections**, accepting a repair only if the data still passes its checks |
| Crawl4AI | It can generate a schema once. It doesn't watch for breakage or repair it |
| Maxun | A full platform to install and host. ScrapeWizard stays a single `pip install` CLI |
| ScrapeGraphAI / LLM scrapers | They pay an LLM on every run. ScrapeWizard uses AI at most once, at build time, and only if you want it |
| Scrapy / Crawlee | They are crawl infrastructure. ScrapeWizard is the thing that writes and maintains the extraction rules; export to them for scale |

A scraper has something a test tool doesn't: **a built-in way to tell whether a repair is
right.** If a healed selector yields 48 products with valid prices like yesterday, it's correct.
If it yields 3 or the prices are empty, it's wrong. That makes self-healing safer here than
anywhere else, and it's the angle to lead with.

---

## 6. Design rules for "lightweight and simple"

1. **Recipe, not code.** The build output is a small YAML/JSON recipe (URL, how to fetch, the
   repeating container, fields with selector ladders and types, pagination, checks). One
   runtime executes any recipe. A recipe can be validated, diffed, healed and hand-edited.
   Exporting a standalone Python script stays available as an option.
2. **Cheapest fetch that works.** Embedded JSON → discovered API → plain HTTP → browser.
3. **AI is optional and used once.** The build works with no key. AI can improve field names or
   untangle a messy page, and it returns a recipe, never free-form code.
4. **One browser session per build**, headless unless the site needs you.
5. **No fake waiting.** Progress reflects real work.
6. **Small core, optional extras.** Excel export, stealth, AI providers and the demo app install
   only when asked for.

Example recipe:

```yaml
name: books
url: https://books.toscrape.com
fetch: auto            # embedded | api | http | browser | auto
collection:
  container: article.product_pod
  fields:
    title:  {select: ["h3 a@title", "h3 a"], type: string}
    price:  {select: ["p.price_color"],      type: money}
    url:    {select: ["h3 a@href"],          type: url}
    image:  {select: ["img@src"],            type: url}
pagination: {type: next_link, select: "li.next a", max_pages: 50}
checks:
  min_records: 20
  required: [title, price]
```

---

## 7. Improvement plan

### Phase 0 — Quick wins (days)
- Remove the artificial sleeps in `_progress_step`; show real step status instead.
- Reuse one browser session for probe and recon; make the probe headless by default and go
  headed only when a block or login is detected.
- Dependency diet:
  - move `pytest*` to a `dev` extra
  - make `pandas` + `openpyxl` an `excel` extra (CSV and JSON need only the standard library)
  - move `fastapi` + `uvicorn` to `dev` (only the demo app and tests use them)
  - keep one spinner/prompt library
  - import LLM SDKs lazily, each behind its own extra
- Fix or mark the failing hardware-detection test.
- **Result:** faster builds, a much smaller install, same features.

### Phase 1 — Recipe format and runtime
- Define the recipe schema (above) and a runtime that executes it: fetch, select, type-convert,
  paginate, dedupe, export.
- `scrapewizard run recipe.yaml` runs one with no build step.
- The LLM path changes to "return a recipe" (validated against the schema) instead of "return
  Python."

### Phase 2 — Build without AI
- `DOMAnalyzer` already finds repeating sections and candidate fields. Turn its output straight
  into a recipe: pick the best collection, infer field types (price, URL, image, date, rating),
  name fields from type and position.
- Use the picker for corrections: click a field to add, rename or remove it.
- `--ai` becomes an opt-in polish step.

### Phase 3 — Fetch ladder
- **Embedded data first:** look for JSON-LD, `__NEXT_DATA__` and similar payloads and map them
  to fields.
- **Discovered API:** when the `Scanner` sees the list coming from a JSON endpoint, offer to
  read the API directly.
- **HTTP:** fetch static pages without a browser and parse with lxml or selectolax.
- **Browser:** fallback only, for pages that need JavaScript or a session.

### Phase 4 — Wire in self-healing, verified by data
- At build time, save a fingerprint for the container and each field.
- At run time, treat **zero records, a failed check or a sharp drop in a field's fill rate** as
  the signal that something changed.
- Heal at the collection level: relocate the container, then the fields inside it.
- Accept a repair **only if the recipe's checks pass again**; otherwise stop and report. Never
  guess silently.
- Record every repair (old selector, new selector, confidence) in the recipe's history.
- Publish the mutation-test numbers (healed / refused / wrong) in the README.

### Phase 5 — Data quality and change detection
- Each run writes a short report: records, valid/invalid, per-field fill rate, duplicates.
- Compare with the previous run and flag drift ("rating fill rate 97% → 88%").
- `scrapewizard check recipe.yaml` exits non-zero when checks fail, so cron or CI can alert.

### Phase 6 — Optional extras (only if asked for)
- `stealth` extra: patchright for the browser, curl_cffi for HTTP.
- More outputs as extras: SQLite, Parquet, webhook.
- "Export to Scrapy spider" for users who need crawling at scale.
- Scheduling: document cron / Task Scheduler rather than building a scheduler.

### Deliberately not building
A distributed crawl engine, URL queue service, job queue, proxy management, hosted workers,
billing, or a dashboard. Those are other products and they'd end "lightweight."

---

## 8. Suggested order and first milestone

Phase 0 → 1 → 2 gives the headline: **`pip install`, point at a URL, get data, no API key.**
Phases 3 and 4 add the two things competitors lack together: the cheapest-fetch ladder and
data-verified healing. Phase 5 turns it into something you can leave running.

---

## Sources

- Scrapling adaptive selectors, tested: https://thunderbit.com/blog/scrapling-review
- Scrapling guide: https://betterstack.com/community/guides/scaling-python/scrapling-adaptive/
- Scrapling docs: https://scrapling.readthedocs.io/en/latest/index.html
- Crawl4AI repository: https://github.com/unclecode/crawl4ai
- Crawl4AI LLM-free schema extraction: https://docs.crawl4ai.com/extraction/llm-strategies/
- Maxun: https://github.com/getmaxun/maxun
- AutoScraper: https://github.com/alirezamika/autoscraper
- Open-source scraper round-ups (star counts): https://www.firecrawl.dev/blog/best-open-source-web-crawler · https://scrapfly.io/blog/posts/best-open-source-web-scrapers · https://www.firecrawl.dev/blog/best-open-source-web-scraping-libraries
- Anti-detect benchmark (nodriver, patchright, camoufox, curl_cffi): https://ianlpaterson.com/blog/anti-detect-browser-benchmark-patchright-nodriver-curl-cffi/
- Stealth browsers compared: https://scrapfly.io/blog/posts/best-stealth-browsers
- Hidden/embedded web data: https://scrapfly.io/blog/posts/how-to-scrape-hidden-web-data
- selectolax benchmark: https://thunderbit.com/blog/selectolax-review · https://apiserpent.com/blog/fastest-python-html-parser-benchmark
- HN: "Web scraping with GPT-4o: powerful but expensive": https://news.ycombinator.com/item?id=41428274
- HN: Show HN LLM Scraper: https://news.ycombinator.com/item?id=40100824
- HN: Show HN Crawl4AI: https://news.ycombinator.com/item?id=46646798
- HN: generating scraper code vs per-page LLM: https://news.ycombinator.com/item?id=40292086
- State of web scraping 2026: https://www.browserless.io/blog/state-of-web-scraping-2026
- Scraping challenges 2026: https://www.promptcloud.com/blog/web-scraping-challenges-and-solutions-2026/
