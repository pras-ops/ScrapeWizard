# 🧙 ScrapeWizard

**Agentic Web Scraper Builder & Self-Healing Automation Studio**

ScrapeWizard is a professional, developer-first platform for building, running, and maintaining reliable web scrapers. By combining high-fidelity browser recording with an offline, multi-tier self-healing engine, ScrapeWizard ensures your scrapers survive target site markup changes and structural mutations without manual code updates.

> [!IMPORTANT]
> **Key Philosophy:** AI helps you *build* and *heal* scrapers—it does *not* execute arbitrary LLM calls during hot paths, ensuring high performance, zero runtime LLM costs, and 100% deterministic scraper execution.

---

## 🚀 Key Features

*   **⚡ ScrapeWizard Studio Dashboard:** A premium, local-first web interface built with React, Tailwind, React Query, and Zustand. Monitor scrape jobs, view run histories, inspect visual diff crops, and review healed steps.
*   **🩺 Multi-Tier Offline Self-Healing:** When site markup breaks, our local engine attempts to heal the broken locator automatically using 5 deterministic similarity tiers (attributes, tag structure, geometry, and parent-child hierarchy) before resorting to AI repairs.
*   **📹 High-Fidelity Recorder:** Interactive recording page featuring full support for frames/iframes, multi-page flows, and automated password-masking (secrets are masked at capture time inside step files and logs).
*   **📊 Unified Decision Gates:** Control scraper behavior upfront through interactive steps:
    *   *Gate 1: Output Format* — Export results directly to CSV, Excel (XLSX), or JSON.
    *   *Gate 2: Pagination Scope* — Control traversal depth (Single page, page limits, or complete crawls).
    *   *Gate 3: Data Quality Firewall* — Monitors extraction output and triggers local self-healing or LLM repair loops if fields become empty.
*   **📦 Zero-Dependency Execution:** Easily packaged as a standard Python wheel containing the bundled frontend. No Node.js runtime is required for end-users.

---

## 🛠️ Installation

```bash
# Install the ScrapeWizard package
pip install scrapewizard

# Install Playwright browser dependencies
playwright install chromium

# Linux/CI environments only:
playwright install-deps
```

---

## 💻 CLI Commands

### 1. `start` - Launch ScrapeWizard Studio
Boots up the FastAPI backend, initializes the database, and launches the React frontend dashboard in your default browser.
```bash
scrapewizard start --port 8000
```

### 2. `login` - Secure Provider Keys
Securely saves your LLM provider keys (OpenAI, Anthropic, OpenRouter, or Ollama) using your system's secure keyring.
```bash
scrapewizard login "sk-or-v1-xyz..."
```

### 3. `setup` - Configure Global Defaults
Configures default LLM providers, active models, and workspace settings.
```bash
scrapewizard setup
```

### 4. `build` - Generate a Scraper
Starts a new scraping project from a target URL.
```bash
# Guided build using default settings
scrapewizard build --url "https://books.toscrape.com"

# Expert Mode: Shows debug logs, database states, and raw model logs
scrapewizard build --url "https://books.toscrape.com" --expert

# Interactive Mode: Ask smart clarification questions about formatting/fields
scrapewizard build --url "https://books.toscrape.com" --interactive
```

### 5. `list` - View Local Projects
Lists all active scraping projects, URLs, execution states, and last modified times.
```bash
scrapewizard list
```

### 6. `resume` - Continue Scraper Builder
Resumes a guide or scraper generation run that was interrupted.
```bash
scrapewizard resume "<PROJECT_ID>"
```

### 7. `doctor` - Environment Diagnostics
Checks Python/OS versions, configuration files, Playwright installations, and validates LLM connection health.
```bash
scrapewizard doctor
```

### 8. `clean` - Cleanup Temporary Workspace
Purges cached test runs and deleted project files to free up disk space.
```bash
scrapewizard clean
```

---

## ⚙️ The Self-Healing Hierarchy (Tiers 0-5)

When a web element mutated (e.g. classes renamed, layout shifted, attributes altered), the ScrapeWizard engine steps through a deterministic self-healing hierarchy to re-identify the element offline:

1.  **Tier 0 (Direct Match):** Evaluates the primary selector.
2.  **Tier 1 (Selector Ladder):** Tries fallback CSS selectors recorded during fingerprinting.
3.  **Tier 2 (Attribute & Text Score):** Computes text content and property matching similarity.
4.  **Tier 3 (Structural Matching):** Evaluates parent/sibling tag relationships.
5.  **Tier 4 (Geometry & Visuals):** Compares coordinates, dimensions, and visual bounds.
6.  **Tier 5 (Navigation Context):** Analyzes step sequence history to infer the correct element.
7.  **Tier 6 (LLM Recovery - Opt-in):** Triggers only if offline tiers fail to find a match above the confidence margin.

> [!TIP]
> To prevent wrong-element matches, the self-healing system requires a strict scoring margin threshold (0.10) between the top match and secondary candidates. Heals are only persisted if the full re-run passes green.

---

## 🏗️ Project Output Structure

Every project created is saved in `~/.scrapewizard/projects/<PROJECT_ID>/` containing:
*   `generated_scraper.py` — The final executable scraper plugin subclassing `BaseScraper`.
*   `storage_state.json` — Cookies and local storage snapshot to bypass logins.
*   `data.json` / `data.csv` — Scraped structured datasets.
*   `analysis_snapshot.json` — Pre-flight DOM audit.
*   `llm_logs/` — Trace of raw AI prompts and responses for debug audit.

---

## 🧪 Golden Test Suite
Verify local setup and self-healing rate by running:
```bash
python3 -m pytest tests/ -v --ignore=tests/golden_sites
```

---

## 📄 License
MIT License
