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

### Known limits

*   Layouts that split one item across two separate rows (Hacker News) need `--like` to say
    which part you want.
*   Self-repair covers the list and its fields. Item-page fields (`detail`) are not repaired yet.
*   Sites that actively block automated browsers are not handled. `--login` is for sites that
    need an account, not for getting past bot checks.
*   Infinite scroll is detected when more pages are asked for (`--all-pages`, `--pages N`).
*   The AI options are tested against a stand-in model only; they have not been run against a
    live AI service in this repository's tests.
*   There is no site-wide crawler. It reads one list, its pages and its items.

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
python -m pytest tests/ -v --ignore=tests/golden_sites
```

---

## 📄 License
MIT License
