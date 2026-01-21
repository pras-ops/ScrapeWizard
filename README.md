# 🚀 ScrapeWizard (MVP-1.0.0)

**CLI-Based Agentic Scraper Builder**

ScrapeWizard automates the creation of web scrapers using LLMs (OpenAI, Anthropic, etc.). It analyzes websites, understands the structure, and generates robust Playwright scrapers that run locally.

## Features

- **Agentic Builder**: Uses LLM to understand DOM and write code.
- **Offline First**: Generated scrapers run locally without AI dependency.
- **Self-Healing**: Automatically attempts to fix broken selectors.
- **Interactive UI**: CLI with rich tables and multi-select fields.
- **CI/CD Ready**: Non-interactive mode via `--ci` flag.
- **Privacy**: Local execution, credentials never sent to cloud.

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Commands & Examples

### 1. `setup` - Configuration
Initial setup to configure your LLM provider and API keys.
```bash
python -m scrapewizard.cli.main setup
```

### 2. `scrape` - Build a Scraper
The main command to start a new scraping project.
```bash
# Basic usage (Tip: Quote the URL if it contains special characters like parentheses)
python -m scrapewizard.cli.main scrape --url "https://books.toscrape.com"

# Non-interactive CI mode (auto-accepts defaults)
python -m scrapewizard.cli.main scrape --url https://books.toscrape.com --ci

# Verbose mode for debugging
python -m scrapewizard.cli.main scrape --url https://books.toscrape.com --verbose
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
- `generated_scraper.py`: The standalone Python Playwright script.
- `data.json` / `data.csv` / `data.xlsx`: Your scraped records.
- `analysis_snapshot.json`: The DOM analysis used by the AI.
- `logs/`: Execution and error logs for debugging.

## Golden Test Suite
To verify the system integrity, run the automated golden tests:
```bash
python tests/golden_sites/books.py
```

## License
MIT
