# 🧙 ScrapeWizard – MVP1

**AI-Assisted Scraper Builder for Developers**

ScrapeWizard is an **AI-powered scraper generator** designed to help developers build reliable Playwright scrapers in minutes. It follows a clear principle: **“AI helps you BUILD scrapers – it does NOT run them.”**

## 🟢 What ScrapeWizard Is Today (v1.2.0)

ScrapeWizard MVP1 is a professional developer tool for rapidly generating maintainable, standalone scrapers.

### Core Capabilities:
- ✅ **Interactive CLI Builder**: Guided process from URL to code.
- ✅ **AI Analysis**: Automatic structure, pattern, and field detection.
- ✅ **Multiple LLM Support**: Choose between OpenAI, Anthropic, OpenRouter, or Local (Ollama) providers.
- ✅ **AI Cost Transparency**: Real-time token tracking and cost estimation for every build.
- ✅ **Smart Assessment**: Pre-flight checks for anti-bot measures.
- **Unified Decision Gates (v1.1)**: Critical checkpoints where the user owns the "WHAT" while the AI handles the "HOW":
    - **Gate 1: Output Format**: Choose CSV, Excel, or JSON upfront.
    - **Gate 2: Pagination Scope**: Define scrape depth (Single page, 5-page limit, or all pages).
    - **Gate 3: Data Quality Firewall**: Monitors extraction results; if missing data is detected, it triggers a recovery loop.
- **Interactive Recovery**: Never get stuck. If a run fails, choose:
    - 🩺 **Auto-Repair**: AI fixes specific selectors for missing fields.
    - 🔄 **Full Retry**: Re-generate the entire strategy from scratch.
- **Scraper Runtime Contract (SRC)**: AI implementation of specific classes only. Infrastructure (Browser, Pagination loop, I/O) is owned by the ScrapeWizard SDK, eliminating hallucinations.
- **Dynamic Waiting**: Automatic handling of hydration delays via `smart_wait()`.
- **Hardening & Portability**: Content-based hashing for deduplication and detailed debug logs indicating exactly why any items were skipped.

## Installation

```bash
pip install -r requirements.txt
playwright install chromium

# Linux Only: Install system dependencies
playwright install-deps

# Optional: only needed if you use the Anthropic provider
pip install anthropic
```

## Commands & Examples

### 1. `login` - Secure API Key Storage
Store your AI providers' API key safely in your system's keyring. No plain text storage.
```bash
scrapewizard login "sk-or-v1-xyz..."
```

### 2. `setup` - Configuration
Initial setup to configure your LLM provider and default model.
```bash
scrapewizard setup
```

### 3. `build` - Create a Scraper
The main command to start a new scraping project.

**Zero-Click Mode (Default - "Just Works"):**
```bash
# Provide URL - ScrapeWizard guides you through simplified format and pagination gates
scrapewizard build --url "https://books.toscrape.com"
```

**Ad-hoc AI Override:**
```bash
# Specify provider and model for a single build session
scrapewizard build --url "https://books.toscrape.com" \
                   --ai-provider anthropic \
                   --ai-model claude-3-5-sonnet-20240620
```

**Interactive Mode (Custom Control):**
```bash
# Ask me "One Smart Question" about fields or format
scrapewizard build --url "https://books.toscrape.com" --interactive
```

**Expert Mode (Full Technical Output):**
```bash
# Shows debug logs, state transitions, LLM warnings, and repair loops
scrapewizard build --url "https://books.toscrape.com" --expert
```

### 4. `list` - View Projects
List all previously created scraper projects.
```bash
scrapewizard list
```

### 5. `resume` - Continue Work
Resume a project that was stopped or failed.
```bash
scrapewizard resume "PROJECT_ID"
```

### 6. `doctor` - Health Check
Verify your environment, dependencies, and LLM connectivity.
```bash
scrapewizard doctor
```

### 7. `clean` - Cleanup
Remove temporary files or old projects to save space.
```bash
scrapewizard clean
```

### 8. `version` - Version Info
Check the current version of ScrapeWizard.
```bash
scrapewizard version
```

---

## ⚙️ Configuration

### Global Config
Stored in `~/.scrapewizard/config.json`. Managed via the `setup` command.

### Local Config Overrides
You can now override global settings (model, provider, etc.) on a per-project basis using a `.scrapewizardrc` file in your project root.

```json
{
  "model": "gpt-4-local-override",
  "provider": "openai"
}
```

## 🏗️ Project Output

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

## 🔭 Project Direction

ScrapeWizard is evolving from a CLI scraper builder into a **local-first UI/UX test automation
platform** (record once → self-healing tests → admin portal), built on the same engine.
The CLI scraper documented above remains the current, working product.

- **[PLATFORM_PLAN.md](PLATFORM_PLAN.md)** — the full roadmap and architecture (source of truth)
- **[BUILD_GUIDE.md](BUILD_GUIDE.md)** — step-by-step how-to for building each stage
- **[FRONTEND_PLAN.md](FRONTEND_PLAN.md)** — detailed spec for the application (the GUI/portal)
- **[APP_BUILD_STEPS.md](APP_BUILD_STEPS.md)** — step-by-step build order: backend API + SQLite, then frontend slices

## License
MIT
