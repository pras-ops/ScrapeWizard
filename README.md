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
  (+2 more columns in the file: url, image)

This list continues on more pages.
Save?  [Enter] this page   [a] all pages   [q] quit
>

Saved  books.csv   20 rows, 4 columns
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
*   **Pagination.** Follows "next" links, numbered pages and `rel="next"`.
*   **Teach by example.** If it picks the wrong list, show it a value you can see on the page:
    `scrapewizard <url> --like "A Light in the Attic"`.
*   **Checks on every run.** A recipe records a minimum row count and required fields.
    `scrapewizard run` exits with an error when they fail, so a scheduler can alert you.
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
```

Each field has a list of selectors tried in order. `@attr` reads an attribute instead of the text.

### Known limits

*   Values that are identical on every item (for example "In stock" everywhere) are treated as
    labels and left out.
*   Layouts that split one item across two separate rows (Hacker News) need `--like` to say
    which part you want.
*   Sites that require a login or block automated access are not handled by this path yet;
    use `scrapewizard build` (below) for those.
*   Self-repair when a site changes is not connected yet. See [SCRAPER_PLAN.md](SCRAPER_PLAN.md).

## 🤖 The AI-assisted builder (optional)

`scrapewizard build --url ...` is the original guided builder. It needs an LLM key (OpenAI,
Anthropic, OpenRouter) or a local Ollama model, writes a standalone Playwright script, and
supports guided access for sites with logins or bot checks.

---

## 🛠️ Installation

```bash
# From source
git clone https://github.com/pras-ops/ScrapeWizard.git
cd ScrapeWizard
pip install -e .

# Browser engine
playwright install chromium

# Linux / CI may also need
playwright install-deps
```

---

## 🚦 Quick start

```bash
# Get the data on a page (asks one question: this page or all pages)
scrapewizard https://books.toscrape.com

# The same without any question, following every page, as JSON
scrapewizard https://books.toscrape.com --all-pages --yes --format json

# Run the saved recipe again later
scrapewizard run books.recipe.yaml
```

---

## 💻 CLI reference

| Command | What it does |
|---|---|
| `scrapewizard <url>` | Look at a page, preview the data, save it with a recipe. Options: `--like VALUE`, `--format csv\|json\|xlsx`, `--pages N`, `--all-pages`, `--out NAME`, `--yes`, `--browser` |
| `scrapewizard run RECIPE` | Run a saved recipe again. Exits with an error if its checks fail |
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
