# 🧙 ScrapeWizard

**A local-first web scraper builder.**

Give ScrapeWizard a URL. It studies the page, works out what data is there, and generates a
standalone Playwright scraper that exports to **CSV, Excel (XLSX), or JSON**. The scraper it
writes is plain Python you own and can run anywhere.

> [!NOTE]
> This repository is scraper-only. The UI/UX testing Studio that briefly lived here is preserved
> on the `archive/ui-testing-studio` branch and is moving to its own repository.

---

## ⚡ What it does today

*   **Guided build:** `scrapewizard build --url ...` walks from a URL to a working scraper and a
    data file.
*   **Page analysis:** detects repeating data (product cards, rows, listings), pagination, the
    tech stack, bot defences and backend API calls.
*   **AI-assisted generation:** an LLM (OpenAI, Anthropic, OpenRouter, or local Ollama) names the
    fields and writes the scraper. An API key or a local model is currently required for `build`.
*   **Guided access:** for sites with logins or bot checks, you browse normally in a real browser
    and ScrapeWizard reuses that session.
*   **Auto-repair:** if the first run returns missing data, the scraper is repaired and re-tested.
*   **Keyring security:** API keys are stored in the system keyring, never in plain text.

## 🧪 In the codebase, not yet wired into `build`

*   **Element engine** (`scrapewizard/engine/`): ranked selector ladders, element fingerprints and
    deterministic self-healing with a confidence threshold and an ambiguity check. It has its own
    tests against a demo app with deliberate page mutations.
*   **Element picker** (`scrapewizard/engine/picker.js`): an in-page point-and-click selector.

Connecting these to generated scrapers is the next step. See [SCRAPER_PLAN.md](SCRAPER_PLAN.md).

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
# 1. Store your LLM key (or run `scrapewizard setup` to pick a provider / local model)
scrapewizard login "sk-..."

# 2. Build a scraper
scrapewizard build --url "https://books.toscrape.com"
```

---

## 💻 CLI reference

| Command | What it does |
|---|---|
| `scrapewizard build --url URL` | Build a scraper project. `--expert` shows debug detail; `--interactive` asks about fields and formats |
| `scrapewizard setup` | Configure the LLM provider, model and proxy |
| `scrapewizard login KEY` | Save an LLM API key in the system keyring |
| `scrapewizard list` | List local scraper projects |
| `scrapewizard resume PROJECT_ID` | Continue an interrupted build |
| `scrapewizard doctor` | Check Python, Playwright, config and LLM connectivity |
| `scrapewizard clean` | Remove old projects and temporary files |
| `scrapewizard version` | Print the installed version |

---

## 🏗️ Where things are stored

* **Config:** `~/.scrapewizard/` (`config.json`, `proxy.json`)
* **Projects:** `~/scrapewizard_projects/<PROJECT_ID>/`
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
