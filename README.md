# 🚀 ScrapeWizard (MVP-1.0.0)

**CLI-Based Agentic Scraper Builder**

ScrapeWizard automates the creation of web scrapers using LLMs (OpenAI, Anthropic, etc.). It analyzes websites, understands the structure, and generates robust Playwright scrapers that run locally.

## Features

- **🧙 Wizard Mode (Default)**: Simple, friendly interface for non-technical users - just give it a URL and get data
- **Stealth Probe Pre-Scan**: Brief headed browser probe (3-5s) to trigger real bot defenses before asking user about access mode
- **Sign-In Detection**: Automatically detects authentication requirements (login buttons, auth prompts) and forces Guided mode for auth-heavy platforms (Amazon, LinkedIn, Facebook, Twitter)
- **Behavioral Analysis**: Measures DOM stability, mutations, and network activity (XHR/API) during recon
- **Unified Guided Access**: Seamlessly handles Login, CAPTCHAs, and complex navigation (e.g. Amazon Search) via a "Guided" headed browser session
- **Bot Defense Scanner**: Automatically detects hostile anti-bot systems (Akamai, DataDome, PerimeterX) and forces "Guided Mode" to ensure success
- **Earned Headless Mode**: Automatically recommends "Guided" mode for complex SPAs, ensuring session stability before attempting headless execution
- **Session Persistence (Storage State)**: Captures cookies, LocalStorage, and SessionStorage to bypass complex auth (JWT/Tokens) autonomously in future runs
- **Agentic Builder**: Uses LLM to understand complex DOM structures and write robust code
- **Offline First & Portable**: Generated scrapers use absolute path discovery, ensuring they run from any directory without AI dependency
- [/] **CI/CD Ready**: Non-interactive mode via `--ci` flag for pipeline integration
- [/] **Interactive Recovery**: Never get stuck. If a script fails, ScrapeWizard offers Auto-Repair, Manual Editing, or a return to configuration settings.
- [/] **Expert Mode**: Full technical output via `--expert` flag for power users and debugging

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

**Wizard Mode (Default - Simple & Friendly):**
```bash
# Just provide the URL - ScrapeWizard handles the rest
python -m scrapewizard.cli.main scrape --url "https://www.amazon.in/s?k=phones"

# What you see: Clean, emoji-driven progress
# 🧙 ScrapeWizard
# Opening the website…
# Checking the website…
# [Interactive prompts if needed]
# 🧠 Understanding this page…
# ✅ Done!
```

**Expert Mode (Full Technical Output):**
```bash
# Shows debug logs, state transitions, LLM warnings, repair loops
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
- `generated_scraper.py`: The standalone Python Playwright script (portable).
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
