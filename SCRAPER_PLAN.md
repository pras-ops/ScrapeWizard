# 🕷️ ScrapeWizard — Scraper Research & Improvement Plan

> Research date: 2026-10-07. Sources: GitHub projects, Hacker News threads, tool docs and
> independent reviews (listed at the end). **Reddit blocks automated access**, so r/webscraping
> could not be read directly; Hacker News and practitioner write-ups stand in for it.
> Every claim about ScrapeWizard's own code was checked against this branch.

## How this plan is organised

| Part | Sections | Answers |
|---|---|---|
| **Background** | §1–§5 | Where the tool stands, what else exists, and the niche to own |
| **Part A — User flow** | §6 | How a person uses it: commands, the one question, what they see |
| **Part B — How the code works** | §7–§10 | Design rules, phased build plan, and techniques to borrow |

Part A comes first on purpose. The user flow is the target, and the code changes in Part B are
chosen because they make that flow possible.

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

## 6. Part A — User flow: how people use it

The engine can be excellent and the tool still feel chaotic. This part defines what the user
sees and does. Part B (§7–§10) exists to make this flow possible.

### 6.1 What using it is like today

| Friction | Today |
|---|---|
| Before first use | Must run `setup` or `login` and have an AI key |
| Commands | 8: `build`, `setup`, `login`, `list`, `resume`, `clean`, `doctor`, `version` |
| Modes | 5 that overlap: default, `--expert`, `--interactive`, `--guided-tour`, `--ci` |
| Questions | Up to 17 different prompts: access mode, browser mode, credentials, save credentials, field mode, field list, pagination, format, "ready?", "continue anyway?", "how does the data look?", which columns are wrong, "proceed?", and two failure menus |
| Surprises | A browser window opens on every build; progress bars that wait on a timer |
| Where results go | `~/scrapewizard_projects/<PROJECT_ID>/output/`, away from where you ran it, under an ID you didn't choose |
| Running again | Find the project folder and run the generated Python file |

### 6.2 Rules for the new flow

1. **One command to a result.** `scrapewizard <url>`, with nothing to set up first.
2. **Show first, ask last.** Do the work, show a preview of the data, then ask one question.
3. **Every question has a flag.** Anything the tool can ask can be answered up front, and
   `--yes` means never ask. Scripts and people use the same command.
4. **Files land where you are.** Data and recipe are saved in the current folder with readable
   names. No hidden project folders, no IDs.
5. **One way of working.** No modes. `-v` shows more detail; that's the only dial.
6. **Say why.** If a browser window opens or something fails, one plain sentence explains it
   and gives the next step.
7. **AI stays out of the way.** It's never required and never asked about unless you pass `--ai`.

### 6.3 The commands

| Command | What it's for |
|---|---|
| `scrapewizard <url>` | Look at a page, preview the data, save it with a recipe |
| `scrapewizard run <recipe>` | Run a saved recipe again. This is what you schedule |
| `scrapewizard edit <recipe>` | Fix what was picked: add, remove or rename fields by clicking on the page |
| `scrapewizard doctor` | Check the installation |

Four commands instead of eight. `setup` and `login` shrink to a one-time key prompt the first
time `--ai` is used. `list`, `resume` and `clean` go away because there are no hidden projects
to manage. `build` stays as an alias for a while so existing users aren't broken.

Common flags, the same on `<url>` and `run`:

| Flag | Meaning |
|---|---|
| `--format csv\|json\|xlsx` | Output type (default: csv) |
| `--pages N` / `--all-pages` | How far to follow pagination (default: first page) |
| `--like "value"` | Teach by example; repeatable |
| `--out NAME` | File name to save as |
| `--yes` | Don't ask anything; accept the defaults |
| `--ai` | Let an AI model help with a messy page |
| `-v` | Show what it's doing in detail |

### 6.4 The main flow: first use

```
$ scrapewizard https://books.toscrape.com

Looking at books.toscrape.com ...
Found 20 items. No browser needed.

  title                   price    in_stock   url
  A Light in the Attic    £51.77   yes        /catalogue/a-light-in-the-attic_1000
  Tipping the Velvet      £53.74   yes        /catalogue/tipping-the-velvet_999
  Soumission              £50.10   yes        /catalogue/soumission_998
  ... 17 more

This list continues for 50 pages.

Save?  [Enter] this page   [a] all pages   [e] edit fields   [q] quit
> 

Saved  books.csv           20 rows, 4 columns
       books.recipe.yaml   run again with: scrapewizard run books.recipe.yaml
```

One command, one question, two files in the current folder. The same thing with no question at
all: `scrapewizard https://books.toscrape.com --all-pages --yes`.

### 6.5 The other situations

**Running it again (or on a schedule)**

```
$ scrapewizard run books.recipe.yaml

books   1,000 rows   12 new, 3 changed, 0 removed since last run
        all checks passed
Saved  books.csv
```

The command exits with an error code when a check fails, so cron, Task Scheduler or CI can
alert without extra tooling.

**It picked the wrong thing**

Either teach by example:
`scrapewizard <url> --like "A Light in the Attic" --like "£51.77"`
or press `e` at the preview (or run `scrapewizard edit books.recipe.yaml`) to click fields on
the page.

**The site needs a login or blocks automation**

```
This site needs you to sign in.
A browser window will open. Sign in as usual, then come back here and press Enter.
```

The session is saved beside the recipe and reused on later runs. The tool warns that this file
contains your login and should not be shared or committed.

**The site changed**

```
$ scrapewizard run books.recipe.yaml

"price" stopped matching (0 of 20 rows).
Repaired: p.price_color -> p.product-price
Checked:  20 rows, every price valid, same count as last run.
Recipe updated. Saved books.csv
```

If a repair can't be verified, it stops instead of guessing:

```
"price" stopped matching and could not be repaired safely (2 possible matches).
Nothing was saved. Fix it with: scrapewizard edit books.recipe.yaml
```

**Nothing was found**

```
Couldn't find a repeating list on this page.
Try:  scrapewizard <url> --like "a value you can see on the page"
  or: scrapewizard <url> --ai
```

### 6.6 How messages are written

- A run ends with at most three lines: what was saved, how many rows, what to do next.
- An error has three parts: what happened, the likely reason, the command to try.
- No raw tracebacks unless `-v` is set; the full detail goes to a log file whose path is shown.
- Progress shows real steps as they happen. Nothing waits on a timer.

### 6.7 Today versus the new flow

| | Today | New |
|---|---|---|
| Setup before first result | AI key required | None |
| Commands | 8 | 4 |
| Modes | 5 | 1 |
| Questions in a normal run | Up to 17 possible | 1 (0 with `--yes`) |
| Browser window | Every build | Only when sign-in or a block needs you, with a reason |
| Output location | Hidden project folder with an ID | Current folder, readable names |
| Run again | Locate and run a generated script | `scrapewizard run <recipe>` |
| When the site changes | Rebuild with AI | Verified self-repair, or a clear stop |

### 6.8 Which phase delivers which part of the flow

| Flow piece | Delivered by (see §8) |
|---|---|
| URL as a plain argument, files in the current folder, no timer waits | Phase 0 |
| `run <recipe>`, retiring hidden projects | Phase 1 |
| Works with no AI key; preview and single question; `--like`; one mode | Phase 2 |
| "No browser needed" fast path; login only when required | Phase 3 |
| "The site changed" repair messages | Phase 4 |
| "12 new, 3 changed" summaries and exit codes for scheduling | Phase 5 |
| `edit` with point-and-click | Phase 2 (basic), refined later |

---

## 7. Part B — How the code should work: design rules

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

## 8. Part B — Improvement plan

### Status (2026-10-07, second pass)

| Phase | State | Done | Still open |
|---|---|---|---|
| 0. Quick wins | Mostly done | CSV and pagination defects fixed; timed progress waits removed; URL as a plain argument; files in the current folder; default install cut from 25 packages to 13, with `ai`, `excel` and `dev` extras | One browser session in the older AI builder; the failing hardware-detection test; lazy loading of the older builder's packages |
| 1. Recipe and runtime | **Done** | Recipe format, typed fields, selector ladders, HTTP runtime, pagination, de-duplication, checks, `run`, one shared HTTP connection | Retiring `list` / `resume` / `clean` |
| 2. Build without AI | **Done** | Builder with no LLM; `--like`; preview and single question; named status values kept; single-class fallbacks; optional AI (`--ai`, `--ask`) that returns a validated recipe | `edit` with point-and-click; removing the older builder's modes |
| 3. Fetch ladder | Partly done | HTTP first, browser fallback, one browser per run; "load more" and infinite scroll; `--login` with a saved session; item pages read JSON-LD and meta tags | Embedded data as the source for a *list* (`__NEXT_DATA__`, JSON-LD item lists); using a discovered API |
| 4. Self-healing | **Done for lists** | Repair by re-finding the data and matching fields against remembered records; verified when known items are found again; refused when a required field cannot be found; history kept in the recipe | Repair of item-page (`detail`) fields; published mutation-test numbers |
| 5. Quality and change detection | Mostly done | Run memory; "N new, N changed, N removed"; checks and exit codes | A per-field quality report; alerts |
| Item pages (was "list → detail", §10 #9) | **Done** | `--follow`: labelled rows, JSON-LD, heading, description; four pages at a time | Repair of these fields |

Tried against live pages: a product grid (with item pages), a quotes list, a 250-item country
list, a table with classed cells, a JavaScript-only page, an infinite-scroll page (100 items in
10 loads) and Hacker News (needs `--like`). Self-repair was exercised live by corrupting a saved
recipe's selectors; it cannot be tested against a real redesign of someone else's site.
The AI options were tested with a stand-in model, not a live service.

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
- Fix the two confirmed defects: CSV export on uneven records and pagination selectors (§10).
- Take the URL as a plain argument and save output in the current folder (§6).
- **Result:** faster builds, a much smaller install, same features.

### Phase 1 — Recipe format and runtime
- Define the recipe schema (above) and a runtime that executes it: fetch, select, type-convert,
  paginate, dedupe, export.
- `scrapewizard run recipe.yaml` runs one with no build step.
- Recipe and data files replace the hidden project folders; `list`, `resume` and `clean` are retired (§6).
- The LLM path changes to "return a recipe" (validated against the schema) instead of "return
  Python."

### Phase 2 — Build without AI
- `DOMAnalyzer` already finds repeating sections and candidate fields. Turn its output straight
  into a recipe: pick the best collection, infer field types (price, URL, image, date, rating),
  name fields from type and position.
- Use the picker for corrections: click a field to add, rename or remove it.
- `--ai` becomes an opt-in polish step.
- Replace the five modes and the prompt sequence with the single preview-and-confirm flow (§6).

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
- `scrapewizard run recipe.yaml` exits non-zero when checks fail, so cron or CI can alert (no separate `check` command; see §6.3).

### Phase 6 — Optional extras (only if asked for)
- `stealth` extra: patchright for the browser, curl_cffi for HTTP.
- More outputs as extras: SQLite, Parquet, webhook.
- "Export to Scrapy spider" for users who need crawling at scale.
- Scheduling: document cron / Task Scheduler rather than building a scheduler.

### Deliberately not building
A distributed crawl engine, URL queue service, job queue, proxy management, hosted workers,
billing, or a dashboard. Those are other products and they'd end "lightweight."

---

## 9. Suggested order and first milestone

Phase 0 → 1 → 2 gives the headline: **`pip install`, point at a URL, get data, no API key.**
Phases 3 and 4 add the two things competitors lack together: the cheapest-fetch ladder and
data-verified healing. Phase 5 turns it into something you can leave running.

---

## 10. Part B — What to borrow, project by project

A second research pass looked at *how* specific projects solve problems ScrapeWizard has. Each
row is a technique to adopt, not a tool to copy.

### Tier 1 — High value, small effort

| # | Technique | Borrowed from | ScrapeWizard today | What to do |
|---|---|---|---|---|
| 1 | **Structured data first** | recipe-scrapers ("wild mode": Schema.org → OpenGraph → site rules), extruct | Ignores JSON-LD, microdata and embedded page data | Before any selector work, read JSON-LD / microdata / OpenGraph / `__NEXT_DATA__`. Product, article, recipe and job pages often need **zero selectors** |
| 2 | **Learn from examples** | AutoScraper (`build(url, wanted_list)`, ~8k stars for this one idea), Scrapling `find_similar` | Needs an LLM to decide what to extract | `scrapewizard build URL --like "A Light in the Attic" --like "£51.77"`: find the nodes holding those values, generalise to their siblings, write the recipe. No AI, no clicking |
| 3 | **Typed values** | price-parser (`"22,90 €"` → amount + currency), dateparser, Crawl4AI's built-in patterns (email, URL, currency, date, phone…) | Every field is named `text_field`, `link` or `image` and exported as raw text | Detect type from the value, name the field after it (`price`, `date`, `email`), and normalise on export |
| 4 | **Run monitors** | Spidermon (item-count minimum, per-field coverage, finish reason, JSON-schema item validation), Scrapy contracts | A one-off "is 80% of data missing?" check during build | Recipe `checks`: minimum records, required fields, per-field coverage thresholds. Evaluated on every run |
| 5 | **Schema validated against the sample** | Crawl4AI `generate_schema(validate=True)`, plus its advice to use 3+ sample pages and avoid `nth-child` | Generated Python is "validated" by running it and hoping | Whatever produces a recipe (heuristics or AI) must be run against the saved page before it's accepted |
| 6 | **Polite by default** | Scrapling / Scrapy AutoThrottle (double the delay when blocked, honour `Retry-After`), robots.txt option | Fixed waits, no backoff | Small throttle in the runtime; respects `Retry-After` |

### Tier 2 — High value, moderate effort

| # | Technique | Borrowed from | ScrapeWizard today | What to do |
|---|---|---|---|---|
| 7 | **Capture the site's own API** | Scrapling `capture_xhr`, mitmproxy2swagger (traffic → API description with inferred path parameters) | `Scanner` logs API URLs and JSON response sizes, then discards them | Keep the JSON bodies. If a response holds an array whose items match the records on the page, offer an **API recipe**: call the endpoint directly and infer the page parameter |
| 8 | **Real pagination detection** | autopager (classifies links as PREV / PAGE / NEXT from link text, class names, URL parts and neighbours) | Matches only the literal text "next", ">" or "»"; no numbered pages, load-more or infinite scroll | Score links on the same features plus `rel="next"` and `aria-label`; detect load-more buttons and scroll-triggered loading |
| 9 | **List → detail pages** | webscraper.io sitemaps (Link selector follows into a child page; Table selector maps headers to columns) | One page type per scraper | `follow:` in the recipe to open each item's link and merge detail fields; a `table` field type |
| 10 | **Shrink the page before any AI call** | dompruner, the Co-Scraper paper, HN advice | Sends the analysis snapshot and more to the model | Strip scripts, styles, hidden nodes, nav and footer; send one sample item, not the page. Reported savings: 50–70% from stripping, a further 30–50% from Markdown |
| 11 | **Change alerts** | changedetection.io (diff between runs, trigger/ignore rules, Apprise for 90+ notification targets) | No run-to-run comparison, no alerts | Diff records against the last run (new / changed / removed); optional `notify` extra using Apprise |
| 12 | **Resume long runs** | Scrapling / Scrapy pause-and-resume checkpoints | A failed paginated run starts over | Save the page cursor and records so far |

### Tier 3 — Nice to have, or experiments

| # | Technique | Borrowed from | Note |
|---|---|---|---|
| 13 | **Pipe-friendly one-liners** | shot-scraper (`shot-scraper javascript URL "…"` prints JSON; YAML for batches) | `scrapewizard get URL` printing JSON to stdout makes it scriptable |
| 14 | **Fetchers as optional extras** | Scrapling (`[fetchers]`: HTTP with browser impersonation, stealth, full browser) | Base install stays tiny; `[browser]`, `[stealth]` add weight only when needed |
| 15 | **Recipe library** | recipe-scrapers (hundreds of site rules), Scrapling's `ShopifySpider` | A `recipes/` folder for common platforms (Shopify `/products.json`, WordPress REST, sitemaps). Community-contributable |
| 16 | **Markdown output** | Crawl4AI, Firecrawl, Scrapling `page.markdown()` | Cheap `--format md` for people feeding LLMs |
| 17 | **MCP server** | Scrapling `[ai]` | Lets AI assistants call ScrapeWizard as a tool. Later |
| 18 | **Lighter browser** | Lightpanda (no rendering; claims up to 9× faster and 16× less memory than Chrome; speaks CDP so Playwright can connect) | Experiment only: site compatibility is still incomplete |

### Defects found while comparing (confirmed by running)

- **CSV export crashes on uneven records.** `scrapewizard_runtime/io.py` takes column names from
  the first record. Writing `[{"title": "A"}, {"title": "B", "price": "9"}]` raises
  `ValueError: dict contains fields not in fieldnames: 'price'`.
- **Pagination detection is unreliable** (`recon/pagination.py`):
  - a plain `<a>Next</a>` yields `a:contains('Next')`, which is not a valid selector
  - a link with class `md:flex next-link` yields `.md:flex.next-link`, also invalid (unescaped colon)
  - numbered page links, `rel="next"` links with an icon, and "Load more" buttons are all
    reported as "no pagination"

### Not worth borrowing

- Scrapling's and Crawlee's spider frameworks, proxy rotation and session pools: that's crawl
  infrastructure. Export to them instead.
- "Bypasses all Cloudflare" style claims: an arms race that would dominate maintenance.
- Per-page LLM extraction (ScrapeGraphAI style): the cost model users complain about most.

### How this changes the phases

- **Phase 1 (recipe):** adopt Crawl4AI-style typed fields (text, attribute, regex, nested, list,
  table) and validate against the saved sample (#5). Fix the CSV defect.
- **Phase 2 (build without AI):** add learn-from-examples (#2) and typed naming (#3). These two
  remove most of the reason an LLM was needed.
- **Phase 3 (fetch ladder):** structured data first (#1) and API capture (#7).
- **Phase 4–5 (healing, quality):** monitors (#4), change alerts (#11), resume (#12).
- **Runtime:** throttle (#6), better pagination (#8), list → detail (#9).

---

## Sources

- AutoScraper: https://github.com/alirezamika/autoscraper
- Crawl4AI LLM-free extraction (schema format, `generate_schema`, regex patterns): https://docs.crawl4ai.com/extraction/no-llm-strategies/
- Scrapling documentation (fetchers, `capture_xhr`, AutoThrottle, checkpoints, MCP): https://scrapling.readthedocs.io/en/latest/index.html
- Spidermon (monitors, field coverage, validation): https://www.zyte.com/blog/giving-spidey-senses-to-your-web-scraping-spiders-using-spidermon/ · https://scrapeops.io/python-scrapy-playbook/extensions/scrapy-spidermon-guide/
- changedetection.io: https://mintlify.com/dgtlmoon/changedetection.io/introduction
- mitmproxy2swagger: https://github.com/alufers/mitmproxy2swagger
- autopager: https://pypi.org/project/autopager/0.1
- recipe-scrapers architecture: https://cdn.jsdelivr.net/npm/recipe-scrapers@1.10.0/docs/architecture.md · https://pypi.org/project/recipe-scrapers/13.31.0
- price-parser: https://pypi.org/project/price-parser
- Zyte open-source libraries overview: https://www.zyte.com/blog/deep-dive-into-zytes-open-source-libraries
- DOM pruning before LLM (Co-Scraper paper, dompruner): https://arxiv.org/pdf/2606.14821 · https://pypi.org/project/dompruner/
- Token reduction for scraping agents: https://www.mindstudio.ai/blog/optimize-web-scraping-skills-ai-agents-token-reduction
- shot-scraper: https://simonwillison.net/2022/Mar/14/scraping-web-pages-shot-scraper
- Lightpanda: https://linuxiac.com/lightpanda-promises-a-faster-lightweight-alternative-to-headless-chrome/
- webscraper.io sitemaps and selector types: https://webscraper.io/blog/scrape-yellowpages.com
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
