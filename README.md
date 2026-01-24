# 🚀 ScrapeWizard (MVP-1.0.0)

**CLI-Based Agentic Scraper Builder**

ScrapeWizard automates the creation of web scrapers using LLMs (OpenAI, Anthropic, etc.). It analyzes websites, understands the structure, and generates robust Playwright scrapers that run locally.

- **🧙 Wizard Mode (Default)**: Simple, "Zero-Click" intelligent agent - just give it a URL and get clean data.
- **Unified Decision Gates (v1.1)**: Critical checkpoints where the user owns the "WHAT" while the AI handles the "HOW":
    - **Gate 1: Output Format**: Choose CSV, Excel, or JSON upfront.
    - **Gate 2: Pagination Scope**: Define scrape depth (Single page, 5-page limit, or all pages).
    - **Gate 3: Data Quality Firewall**: Monitors extraction results; if missing data is detected, it triggers a recovery loop.
- **Interactive Recovery**: Never get stuck. If a run fails, choose:
    - 🩺 **Auto-Repair**: AI fixes specific selectors for missing fields.
    - 🖐️ **Guided Mode**: Re-run with a visible browser for manual corrections.
    - 🔄 **Full Retry**: Re-generate the entire strategy from scratch.
- **Scraper Runtime Contract (SRC)**: AI implementation of specific classes only. Infrastructure (Browser, Pagination loop, I/O) is owned by the ScrapeWizard SDK, eliminating hallucinations.
- **Dynamic Waiting**: Automatic handling of hydration delays via `smart_wait()`.
- **Hardening & Portability**: Content-based hashing for deduplication and detailed debug logs indicating exactly why any items were skipped.

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Commands & Examples

### 1. `auth` - Secure API Key Storage
Store your AI providers' API key safely in your system's keyring. No plain text storage.
```bash
python -m scrapewizard.cli.main auth sk-or-v1-xyz...
```

### 2. `setup` - Configuration
Initial setup to configure your LLM provider and default model.
```bash
python -m scrapewizard.cli.main setup
```

### 2. `scrape` - Build a Scraper
The main command to start a new scraping project.

**Zero-Click Mode (Default - "Just Works"):**
```bash
# Provide URL - ScrapeWizard guides you through simplified format and pagination gates
python -m scrapewizard.cli.main scrape --url "https://www.amazon.in/s?k=phones"

# Interaction Flow:
# ? Output Format: Excel
# ? Pagination Strategy: Limit to 5 Pages
# ...
# ✓ Found 5 data fields: title, price, image...
# 🩺 Quality Check: Success!
# ⚡ Scraped 31 items → Saved to data.xlsx
# ✅ Done!
```

**Interactive Mode (Custom Control):**
```bash
# Ask me "One Smart Question" about fields or format
python -m scrapewizard.cli.main scrape --url "https://books.toscrape.com" --interactive
```

**Expert Mode (Full Technical Output):**
```bash
# Shows debug logs, state transitions, LLM warnings, repair loops, and full manual control
python -m scrapewizard.cli.main scrape --url "https://books.toscrape.com" --expert
```

**CI Mode (Non-Interactive):**
```bash
# Auto-accepts defaults, no prompts
python -m scrapewizard.cli.main scrape --url https://books.toscrape.com --ci
```

### 3. `list` - View Projects
List all previously created scraper projects.
```bash
python -m scrapewizard.cli.main list
```

### 4. `resume` - Continue Work
Resume a project that was stopped or failed.
```bash
python -m scrapewizard.cli.main resume
```

### 5. `doctor` - Health Check
Verify your environment, dependencies, and LLM connectivity.
```bash
python -m scrapewizard.cli.main doctor
```

### 6. `clean` - Cleanup
Remove temporary files or old projects to save space.
```bash
python -m scrapewizard.cli.main clean
```

### 7. `version` - Version Info
Check the current version of ScrapeWizard.
```bash
python -m scrapewizard.cli.main version
# OR
python -m scrapewizard.cli.main --version
```

## Project Output

Projects are saved in `~/scrapewizard_projects/`.
Each project contains a self-contained `output/` folder:
- `generated_scraper.py`: The ScrapeWizard Scraper Plugin (subclasses `BaseScraper`).
- `storage_state.json`: Full session state (Cookies + LocalStorage) for manual bypass/login.
- `data.json` / `data.csv` / `data.xlsx`: Your scraped records (cleaned and filtered).
- `analysis_snapshot.json`: The raw DOM analysis used by the AI.
- `llm_logs/`: Raw AI responses for deep debugging and transparency.

## Golden Test Suite
To verify the system integrity, run the automated golden tests:
```bash
python tests/golden_sites/books.py
```

## License
MIT
