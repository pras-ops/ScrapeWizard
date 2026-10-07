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
*   **Typed, named fields.** Prices, numbers, dates, links and images are recognised and named.
    Each link is named after the text it belongs to (`url`, `author_url`, `comments_url`).
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
| BBC News | Right: 47 headlines |
| Wikipedia, countries by population | Right: 240 rows, columns named from the headings. Plain HTTP was refused; the browser fallback handled it |
| Real Python | Right: 18 articles, through the browser fallback |
| quotes.toscrape.com/tableful | Partly: the rows are found, but the quote and its tags alternate in one column |
| scrapethissite.com frames page | Wrong: the data is inside a frame, so it picks the menu |
| PyPI search | Nothing: the site answers with a bot check |
| Stack Overflow questions | Nothing: refused over HTTP and in the browser |

**10 of 14 right, 1 partly, 3 not.** Finding the list takes about a second or less on each,
including the 1.7 MB Wikipedia page.

The weak spot is **column names**, not the data. On sites that use utility or generated class
names (GitHub, BBC) the title, links, dates and prices are named, and the rest come out as
`text`, `text_2`, `number`. Three ways to fix that:

*   rename the keys in the recipe file (it is plain YAML),
*   pass `--ai` to let a model suggest names once, or
*   pass `--ask "repository, description, language, stars"` to say what you want.

### Known limits

*   **Bot protection.** Sites that refuse automated browsers (PyPI search, Stack Overflow) are
    not handled. `--login` is for sites that need an account, not for getting past bot checks.
*   **Frames.** Data inside an `<iframe>` is not read. Point it at the frame's own address.
*   **Generated class names.** They are avoided when recognised, but some slip through
    (`div.jeApUG` on BBC). Such a recipe stops matching at the site's next release; `run` then
    repairs it from the last run's data.
*   **Records that alternate in a class-less table** come out as one column.
*   **Self-repair** covers the list and its fields. Item-page fields (`detail`) are not repaired yet.
*   **Lists delivered only as JSON** (an API behind the page) are read from the rendered page,
    not from the API.
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
| `scrapewizard build --url URL` | AI-assisted builder. `--expert` shows debug detail; `--interactive` asks about fields and formats |
| `scrapewizard setup` | Configure the LLM provider, model and proxy |
| `scrapewizard login KEY` | Save an LLM API key in the system keyring |
| `scrapewizard list` | List local scraper projects |
| `scrapewizard resume PROJECT_ID` | Continue an interrupted build |
| `scrapewizard doctor` | Check Python, Playwright, config and LLM connectivity |
| `scrapewizard clean` | Remove old projects and temporary files |
| `scrapewizard version` | Print the installed version |

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

182 tests, all offline: every page they read is served from the test's own machine. Some start
a real browser, which is why the browser install is needed.

## 📚 More

* [learn.md](learn.md): how it works inside, module by module.
* [SCRAPER_PLAN.md](SCRAPER_PLAN.md): the research behind it, the plan, and what is done and open.

---

## 📄 License
MIT License
