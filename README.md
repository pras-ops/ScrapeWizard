# 🧙 ScrapeWizard

**Point it at a page, get the data. No AI key needed.**

```
$ scrapewizard https://books.toscrape.com

Looking at books.toscrape.com ...
Found 20 items. No browser needed.

 title                      │ price
────────────────────────────┼────────
 A Light in the Attic       │ £51.77
 Tipping the Velvet         │ £53.74
 Soumission                 │ £50.10
 Sharp Objects              │ £47.82
 Sapiens: A Brief History … │ £54.23
  ... 15 more
  (+3 more columns in the file: availability, url, image)

This list continues on more pages.
Save?  [Enter] this page   [a] all pages   [q] quit
>

Saved  books.csv   20 rows, 5 columns
       books.recipe.yaml   run again with: scrapewizard run books.recipe.yaml
```

ScrapeWizard finds the repeating data on a page (product cards, table rows, listings), works out
the fields, and saves two files in the folder you are in: the data, and a small readable
**recipe** you can run again, edit by hand, or schedule.

> [!NOTE]
> This repository is scraper-only. The UI/UX testing Studio that briefly lived here is preserved
> on the `archive/ui-testing-studio` branch and is moving to its own repository.

---

## ⚡ What it does

*   **No setup, no AI key.** The page is analysed locally.
*   **Plain HTTP first.** A browser is started only when a page needs JavaScript to show its data.
*   **Data embedded in the page.** Many JavaScript sites ship their list as JSON inside the page
    (`__NEXT_DATA__`, JSON-LD, `var data = [...]`). That is read directly: no browser, and no
    selectors to break.
*   **Typed, named fields.** Prices, numbers, dates, links and images are recognised and named.
    Each link is named after the text it belongs to (`url`, `author_url`, `comments_url`).
*   **Names from the page, not from a model.** Where class names say nothing, columns are named
    from what the page says: `itemprop`, test markers, where a link goes (`.../stargazers`),
    the words after a number ("12 stars today"), "3 hours ago" (`age`).
*   **Selectors that last.** Test markers (`data-testid`) are preferred, and class names made up
    by a build tool (`jeApUG`) are not used.
*   **Frames.** If the list sits in a frame of the same site, it is read from the frame.
*   **Tables.** The heading row becomes the column names. Works on tables with no classes at all.
*   **Records in two parts.** A title row followed by a details row (Hacker News), or a `dt`
    followed by its `dd` (arXiv), is read as one row.
*   **All the pages.** Follows "next" links, numbered pages, "load more" buttons and infinite scroll.
*   **Item pages.** `--follow` opens each item's own page and adds what it holds: labelled rows,
    embedded structured data, the description.
*   **Teach by example.** If it picks the wrong list, show it a value you can see on the page:
    `scrapewizard <url> --like "A Light in the Attic"`.
*   **Remembers each run.** `scrapewizard run` reports "12 new, 3 changed, 0 removed since last run".
*   **Repairs itself.** When a site changes and the recipe stops matching, the page is searched
    again and the repair is checked against the last run's data. If it can't be checked, it stops
    instead of guessing.
*   **Checks on every run.** A minimum row count and required fields. `run` exits with an error
    when they fail, so a scheduler can alert you.
*   **Signed-in sites.** `--login` lets you sign in once in a browser window and reuses the session.
*   **Optional AI.** `--ask "job titles and salaries"` or `--ai`, using your own key or a local
    model. Used once, to write the recipe. Running a recipe never uses AI.
*   **CSV, JSON or Excel** output (`--format`).

### A recipe

```yaml
name: books
url: https://books.toscrape.com
fetch: http
collection:
  container: article.product_pod
  fields:
    title: {select: ["h3 > a@title"], type: text}
    price: {select: ["p.price_color"], type: money}
    url:   {select: ["div.image_container > a@href", "h3 > a@href"], type: url}
pagination: {type: next_link, select: "li.next > a", max_pages: 3}
checks: {min_records: 30, required: [title, price]}
detail:                       # only with --follow
  follow: url
  fields:
    upc:         {select: ['th:-soup-contains("UPC") + td'], type: text}
    description: {select: ["#product_description + p"], type: text}
```

Each field has a list of selectors tried in order. `@attr` reads an attribute instead of the text.
Item-page fields may also read embedded data (`jsonld:offers.price`) or a meta tag (`meta:description`).

When the list comes from data embedded in the page, the container starts with `data:` and the
fields are paths instead of selectors:

```yaml
collection:
  container: data:props.pageProps.products
  fields:
    title: {select: [name], type: text}
    price: {select: [price.amount], type: number}
    image: {select: [images.0.url], type: image}
```

Run memory and any saved sign-in are kept in a `.scrapewizard/` folder beside the recipe. That
folder ignores itself in git.

### How well it works

Measured on 7 October 2026 against 14 public pages that were **not** used while building the
tool, with no AI and no `--like` hint. "Right" means it chose the list a person would want and
every row came out.

| Page | Result |
|---|---|
| GitHub trending | Right: 12 repositories |
| python.org blogs | Right: 14 posts |
| arXiv recent papers | Right: 50 papers, each read from a `dt` and the `dd` after it |
| Hacker News jobs | Right: 30 jobs |
| Lobsters | Right: 25 stories |
| Project Gutenberg search | Right: 25 books |
| dev.to | Right: 17 posts |
| BBC News | Right: 47 headlines, through the site's own test markers |
| Wikipedia, countries by population | Right: 240 rows, columns named from the headings. Plain HTTP was refused; the browser fallback handled it |
| Real Python | Right: 18 articles, through the browser fallback |
| scrapethissite.com frames page | Right: 14 rows, read from the frame |
| quotes.toscrape.com/tableful | Partly: the rows are found, but the quote and its tags alternate in one column |
| PyPI search | Nothing: the site answers with a bot check |
| Stack Overflow questions | Nothing: refused over HTTP and in the browser |

**11 of 14 right, 1 partly, 2 not** (both behind bot protection). Finding the list takes about
a second or less on each, including the 1.7 MB Wikipedia page.

Column names, on a site whose classes are all styling (GitHub trending):

| Before | Now |
|---|---|
| `title, text, text_2, number, number_2, text_3` | `title, description, programming_language, stargazers, forks, stars_today` |

Not every column gets a good name. Where the page says nothing about a value, it is still
`text` or `number`. Three ways to fix that:

*   rename the keys in the recipe file (it is plain YAML),
*   pass `--ai` to let a model suggest names once, or
*   pass `--ask "repository, description, language, stars"` to say what you want.

A JavaScript-drawn page (quotes.toscrape.com/js) that used to need a browser now gives all 100
quotes over 10 pages with plain HTTP, read from the data embedded in each page.

### Known limits

*   **Bot protection.** Sites that refuse automated browsers (PyPI search, Stack Overflow) are
    not handled, and this tool does not try to get around them. `--login` is for sites that
    need an account, not for getting past bot checks.
*   **Lists loaded from an API after the page opens** are read from the page a browser draws.
    The API itself is not called directly yet.
*   **Embedded data** is read only when it is real JSON. Data written as JavaScript code
    (unquoted keys, Next.js "app router" streams) is not; those pages fall back to the browser.
*   **Records that alternate in a class-less table** come out as one column.
*   **One main link per row.** When a site marks some cards' links differently, a few rows can
    come out without a `url` (4 of 47 on BBC News).
*   **Self-repair** covers the list and its fields. Item-page fields (`detail`) are not repaired yet.
*   **Infinite scroll** is detected when more pages are asked for (`--all-pages`, `--pages N`).
*   **Not verified live:** the AI options were tested with a stand-in model, `--login` with a
    scripted sign-in, and self-repair by damaging a saved recipe. None of the three has been run
    against a real AI service, a real account or a real redesign in this repository's tests.
*   **No site-wide crawler.** It reads one list, its pages and its items.

## 🤖 The AI-assisted builder (older, optional)

`scrapewizard build --url ...` is the original guided builder. It needs an LLM key (OpenAI,
Anthropic, OpenRouter) or a local Ollama model and writes a standalone Playwright script.

---

## 🛠️ Installation

```bash
# From source
git clone https://github.com/pras-ops/ScrapeWizard.git
cd ScrapeWizard
pip install .

# Only needed for pages that require JavaScript, --login, "load more" and infinite scroll
playwright install chromium

# Optional extras
pip install ".[excel]"   # --format xlsx
pip install ".[ai]"      # --ai, --ask and the AI-assisted builder
pip install ".[dev]"     # running the tests
```

---

## 🚦 Quick start

```bash
# Get the data on a page (asks one question: this page or all pages)
scrapewizard https://books.toscrape.com

# Every page, plus each item's own page, without any question, as JSON
scrapewizard https://books.toscrape.com --all-pages --follow --yes --format json

# Run the saved recipe again later: reports what changed, repairs itself if the site changed
scrapewizard run books.recipe.yaml

# A site that needs an account
scrapewizard https://example.com/orders --login
```

---

## 💻 CLI reference

| Command | What it does |
|---|---|
| `scrapewizard <url>` | Look at a page, preview the data, save it with a recipe. Options: `--like VALUE`, `--follow`, `--pages N`, `--all-pages`, `--format csv\|json\|xlsx`, `--out NAME`, `--yes`, `--browser`, `--login`, `--ai`, `--ask TEXT` |
| `scrapewizard run RECIPE` | Run a saved recipe again: reports changes, repairs itself if the site changed, exits with an error if its checks fail. Options: `--pages N`, `--all-pages`, `--format`, `--out NAME`, `--no-repair` |
| `scrapewizard doctor` | Check Python, Playwright, config and LLM connectivity |
| `scrapewizard setup` | Only for the optional AI help: choose the provider and model |
| `scrapewizard login KEY` | Only for the optional AI help: save an API key in the system keyring |
| `scrapewizard version` | Print the installed version |

The older AI-assisted builder (`build`, `list`, `resume`, `clean`) still works but is no longer
shown in `--help`.

---

## 🏗️ Where things are stored

* **`scrapewizard <url>` and `run`:** the data file and `<name>.recipe.yaml` are saved in the
  current folder.
* **Config (AI builder):** `~/.scrapewizard/` (`config.json`, `proxy.json`)
* **AI builder projects:** `~/scrapewizard_projects/<PROJECT_ID>/`
  * `generated_scraper.py`: the scraper
  * `output/`: extracted data (JSON, CSV, XLSX)
  * `session.json`: build state
  * `llm_logs/`: prompts and raw model output, for auditing

---

## 🧪 Tests

```bash
pip install -r requirements.txt
playwright install chromium
python -m pytest tests/ -v --ignore=tests/golden_sites
```

202 tests, all offline: every page they read is served from the test's own machine. Some start
a real browser, which is why the browser install is needed.

## 📚 More

* [learn.md](learn.md): how it works inside, module by module.
* [SCRAPER_PLAN.md](SCRAPER_PLAN.md): the research behind it, the plan, and what is done and open.

---

## 📄 License
MIT License
