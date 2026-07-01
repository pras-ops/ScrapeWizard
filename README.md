# 🧙 ScrapeWizard

**The Local-First, Self-Healing Web Scraper Builder & UI/UX Test Automation Studio**

ScrapeWizard is a professional, developer-first toolkit for building, executing, and maintaining reliable web automation workflows. By combining high-fidelity browser recording with an offline, multi-tier self-healing engine, ScrapeWizard ensures your scrapers and test suites survive target site markup changes, class renames, and structural mutations without manual script updates.

> [!IMPORTANT]
> **Key Philosophy:** AI is an *optional enhancer* to help you name steps and recover from layout shifts. It is **never** on the runtime hot-path. If target pages haven't mutated, runtime AI cost is **$0.00**, ensuring high performance, zero runtime LLM costs, and 100% deterministic scraper/test execution.

---

## 🚀 Two Products, One Unified Engine

Built atop a shared core that tracks deep element fingerprints (tag names, semantic attributes, structural relationships, geometry, and navigation history), ScrapeWizard supports two major developer use-cases:

1. **📦 Product A: Scraper Studio:** Build high-performance data pipelines that export target pages to **CSV, Excel (XLSX), or JSON** with zero-click configuration.
2. **🧪 Product B: UI/UX Test Automation:** Record workflows once to generate standard **Playwright + pytest** suites. Run them headless in CI with automatic checks for **accessibility (a11y), visual regressions (visual diffs), console errors, and network failures**.

---

## ⚡ Key Features

*   **🖥️ ScrapeWizard Studio Dashboard:** A premium, local-first web dashboard built with FastAPI and React. Monitor execution queues, visualize run histories step-by-step, review accessibility violations, inspect visual diff crops, and approve or reject healed locators.
*   **🩺 Multi-Tier Offline Self-Healing (Tiers 0-5):** When page markup changes, our local engine attempts to locate the element automatically using 5 deterministic similarity tiers (attributes, tag structure, geometry, and parent-child hierarchy) with **zero LLM/API calls**.
*   **📹 High-Fidelity Flow Recorder:** Launches an interactive headed browser context to capture user interactions (clicks, text input, navigation, scroll) along with element fingerprints. Featuring full support for multi-page flows and automatic masking of password inputs.
*   **🔬 Isolated Sandbox Runner:** Executes flows in clean Playwright contexts, collecting visual screen diffs, console warnings, and network error signals.
*   **♿ Automated Accessibility (a11y) Audits:** Injects `axe-core` dynamically during runtime sandbox executions to find markup, color contrast, and ARIA violations per step.
*   **📦 Zero Lock-in Pytest Export:** Export flows directly to standalone Python scripts. The generated files are completely independent of the platform and can run in any standard CI environment.
*   **🔑 Keyring Security:** Securely stores LLM provider API keys (OpenAI, Anthropic, OpenRouter, and Ollama) using the system's secure keyring.

---

## 🛠️ Installation & Setup

```bash
# 1. Install ScrapeWizard and its dependencies
pip install scrapewizard

# 2. Install Playwright browser engines
playwright install chromium

# Note: On Linux/CI systems, you may also need:
playwright install-deps
```

---

## 🚦 Getting Started in 60 Seconds

### 1. Record a Workflow
Launch a headed browser to record user interactions on a page and capture detailed element fingerprints:
```bash
scrapewizard record --url "https://books.toscrape.com" --output login_flow.json
```

### 2. Run Quality Checks & Sandbox
Execute the recorded workflow headless to check console logs, network errors, accessibility violations, and visual regressions:
```bash
scrapewizard test login_flow.json
```

### 3. Build a Scraper Project
Generate a programmatic scraper script from a target URL with guided options:
```bash
scrapewizard build --url "https://books.toscrape.com"
```

### 4. Launch the Web Studio
Open the local FastAPI web dashboard to manage your tests, runs, and configurations:
```bash
scrapewizard start --port 8000
```

---

## 💻 CLI Commands Reference

### 1. `start` - Launch Web Studio Dashboard
Boots up the FastAPI backend and opens the React web dashboard in your default browser.
```bash
scrapewizard start [--port PORT] [--no-open]
```

### 2. `record` - Record User Interactions
Opens a headed browser to capture user events and element fingerprints, saving them to a JSON file.
```bash
scrapewizard record --url URL [--output OUTPUT_JSON] [--screenshots SCREENSHOT_DIR]
```

### 3. `test` - Run Sandbox Quality Checks
Runs a headless sandbox execution of the recorded flow, collecting quality signals (console, network, a11y, visual diff).
```bash
scrapewizard test FLOW_JSON [--artifacts ARTIFACT_DIR] [--headed]
```

### 4. `build` - Generate Scraper
Builds a new scraping project from a URL.
```bash
# Standard guided scraper builder
scrapewizard build --url URL

# Expert Mode: Shows debug logs, database states, and raw model logs
scrapewizard build --url URL --expert

# Interactive Mode: Prompts smart questions about target fields and formats
scrapewizard build --url URL --interactive
```

### 5. `setup` - Configure Global Settings
Interactively configures default LLM providers, active models, active proxies, and settings.
```bash
scrapewizard setup [--provider PROVIDER] [--api-key KEY] [--model MODEL] [--use-proxy]
```

### 6. `login` - Secure Provider Keys
Saves your LLM provider API keys securely in the system keyring.
```bash
scrapewizard login "sk-..."
```

### 7. `list` - View Local Projects
Lists all active scraper projects, target URLs, states, and modification times.
```bash
scrapewizard list
```

### 8. `resume` - Continue Scraper Builder
Resumes an interrupted scraper construction or guided tour session.
```bash
scrapewizard resume PROJECT_ID
```

### 9. `doctor` - Environment Diagnostics
Checks Python version, configuration files, Playwright installation, projects directory, and LLM connection health.
```bash
scrapewizard doctor
```

### 10. `clean` - Cleanup Temporary Workspace
Purges cached test runs, build logs, and deleted project files to free up disk space.
```bash
scrapewizard clean [--force]
```

### 11. `version` - Show Version
Prints the installed version of ScrapeWizard.
```bash
scrapewizard version
```

---

## ⚙️ The Self-Healing Hierarchy (Tiers 0-6)

When a web element mutates (e.g. classes renamed, layout shifted, attributes altered), the ScrapeWizard engine steps through a deterministic self-healing hierarchy to re-identify the element offline:

1. **Tier 0 (Direct Match):** Evaluates the primary selector.
2. **Tier 1 (Selector Ladder):** Tries fallback CSS selectors recorded during fingerprinting.
3. **Tier 2 (Attribute & Text Score):** Computes similarity score of attribute overlap and normalized inner text.
4. **Tier 3 (Structural Matching):** Evaluates parent/sibling tag relationships and sibling offsets.
5. **Tier 4 (Geometry & Visuals):** Compares relative viewport coordinates (x/y percentages) and dimensions.
6. **Tier 5 (History & Navigation):** Checks past successful element resolutions from historical runs.
7. **Tier 6 (LLM Recovery - Opt-in):** Triggers only if all offline tiers fail. Sends a compact DOM snippet to the LLM to locate the element, verifying the proposed selector by re-running the step.

> [!TIP]
> To prevent wrong-element matches (false positives), the self-healing system requires a strict scoring margin threshold between the top match and secondary candidates. Heals are only persisted if the full re-run completes successfully.

---

## 🏗️ Workspace Directory Structure

All global configurations and local scraping/testing projects are stored locally on your machine:

* **Global Configuration:** Saved in `~/.scrapewizard/`
  * `config.json` — Active LLM provider, default model, and settings.
  * `proxy.json` — Configured proxies.
* **Scraper Projects Root:** Saved in `~/scrapewizard_projects/`
  * Contains individual `<PROJECT_ID>/` directories with:
    * `session.json` — Project execution state and metadata.
    * `generated_scraper.py` — The final Python scraper script.
    * `llm_logs/` — Prompts and raw completion text for auditing.
    * `output/` — Extracted datasets (JSON, CSV, XLSX).
* **Test Baselines & Runs:**
  * `~/.scrapewizard/baselines/` — Baseline screenshots for visual regression tests.
  * Run artifacts (screenshots, visual diffs, and test report logs) are saved in the configured output directories.

---

## 🧪 Running Unit Tests
Verify the local installation and self-healing efficacy by executing:
```bash
python3 -m pytest tests/ -v --ignore=tests/golden_sites
```

---

## 📄 License
MIT License
