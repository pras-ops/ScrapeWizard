# 🎓 Learning ScrapeWizard: How it was Built

ScrapeWizard is an **Agentic Web Scraper Builder**. Unlike traditional scrapers where you write selectors manually, ScrapeWizard uses AI to understand the page structure, write the code, and even fix itself if the code fails.

**Two Modes:**
- **🧙 Wizard Mode (Default)**: A clean, "UX Firewall" experience for non-technical users. It suppresses all internal engine diagnostics, технические scores, and LLM signals, focus solely on the end result.  
- **🔧 Expert Mode (`--expert`)**: Full technical transparency. Shows the raw engine internals, complexity/hostility scores, state transitions, and detailed LLM debug logs.

This document breaks down the architecture, the logic, and the exact prompts used to build it.

---

## 🏗️ 1. Core Architecture

The project follows a **Modular State Machine** architecture. Each step of the process is isolated into a "Phase".

### ❄️ MVP1 Freeze + Bridge Injection
As we pivot from the CLI (MVP1) to the Desktop Studio (MVP2), we follow a **risk-minimized** philosophy:
- **MVP1 Freeze**: The core CLI agents (`Analyst`, `CodeGen`, `Repair`) are frozen to maintain stability for existing users.
- **Bridge Injection**: New bridge commands (`studio`, `record`, `test`) are "injected" into the CLI as isolated modules.
- **Studio Isolation**: All MVP2-specific logic resides in the `studio/` directory, importing MVP1 as a library rather than refactoring it.

### The "Phase" Workflow (State Machine)
1.  **INIT (Stealth Probe Pre-Scan)**: Headed browser probe (3-5s) to detect bot defenses and sign-in requirements, then recommend access mode.
2.  **GUIDED_ACCESS**: If hostile or auth-heavy, user manually navigates (Login, Filter, Search) in a headed browser.
3.  **RECON**: Playwright opens the site, performs a **Behavioral Scan** (stability, mutations, scroll dependency), and extracts a snapshot.
4.  **INTERACTIVE_SOLVE**: If a CAPTCHA is detected, the system pauses for manual human bypass and captures session cookies.
5.  **LLM_ANALYSIS**: AI looks at the DOM AND the Scan Profile to see if it's scrapable.
6.  **USER_CONFIG (Decision Gates 1 & 2)**: 
    - **Gate 1**: User selects output format (CSV, XLSX, JSON).
    - **Gate 2**: User defines pagination scope (e.g., Limit to 5 pages).
7.  **CODEGEN**: AI implementation of the **Scraper Runtime Contract (SRC)**. It subclasses `BaseScraper` from `scrapewizard_runtime`.
8.  **TEST & REPAIR (Gate 3 - Quality Firewall)**: 
    - The script runs. If it fails or produces >80% missing data, the **Quality Firewall** pauses execution.
    - Options: 🩺 **Auto-Repair**, 🖐️ **Re-guided Access**, or 🔄 **Configuration Change**.
9.  **REPAIR LOOP**: If "Auto-Repair" is chosen, the AI performs **Bulletproof Contract** fixes with column-specific hints.
10. **HARDENING (Phase 6)**: The runtime enforces content-based hashing for robust deduplication and structural guardrails for LLM-generated entry points.
11. **FINAL_RUN**: The polished plugin runs via the ScrapeWizard SDK, managing the pagination loop and multi-format saving automatically.

---

## 🧠 2. The "Brains" (LLM Agents)

We used three specialized "Agents" instead of one giant prompt. This makes the system more reliable.

### Agent A: The Analyst (UnderstandingAgent)
**Goal**: Look at thousands of lines of HTML + Behavioral signals and find the "interesting" parts.
**How it works**: We send a structured JSON "Snapshot" + a "Scan Profile" (mutation rates, framework detection). This helps the AI decide if the site is a static page or a complex React SPA.

**The Prompt**:
```python
SYSTEM_PROMPT_UNDERSTANDING = """
You are an expert web scraping analyst. 
Analyze the provided JSON snapshot of a webpage's DOM structure AND its behavioral scan profile.
The Scan Profile provides insights into: DOM stability, mutations, scroll dependency, and anti-bot signals.
"""
```

### Agent B: The Plugin Developer (CodeGenerator)
**Goal**: Write a scraper implementation using the ScrapeWizard SDK.
**The Scraper Runtime Contract (SRC)**: We forbid the AI from touching infrastructure (Playwright setup, files, retries, pagination loops).
- **AI owns selection**: The LLM writes logic to find the "Next" button and extract fields.
- **SDK owns execution**: The `BaseScraper` handles clicking the "Next" button, page counters, and saving formatted data.

**The Prompt**:
```python
SYSTEM_PROMPT_CODEGEN = """
You MUST:
- Subclass `BaseScraper`
- Implement `navigate()`, `get_items()`, and `parse_item()`
- Use `await self.runtime.smart_wait()` for dynamic stability.
- **CRITICAL**: Maintain the `if __name__ == "__main__":` entry point.
"""
```

### Agent C: The Plugin Doctor (RepairAgent)
**Goal**: Fix the plugin logic if it fails.
**Contract Enforcement**: The agent fixes selectors or DOM traversal but is strictly prohibited from modifying the browser runtime.

**The Prompt**:
```python
SYSTEM_PROMPT_REPAIR = """
You MUST fix the provided scraper plugin (subclass of `BaseScraper`).
Ensure selector stability and fix logic errors.
"""
```

---

## 🛠️ 3. Technical Low-Level Details

### 1. Stealth Probe Pre-Scan & Sign-In Detection
**The Problem**: Bot defenses (Akamai, PerimeterX) don't activate in headless mode. Amazon hides its defenses until you browse.

**The Solution**:
- **Stealth Probe**: Pre-Scan uses a brief headed browser (headless=False) with `--disable-blink-features=AutomationControlled` to trigger real bot defenses.
- **Sign-In Detection**: Scans for login buttons (`a[href*="login"]`, `a[id*="nav-link-accountList"]`), auth prompts ("sign in to continue"), and known auth-heavy platforms (Amazon, LinkedIn).
- **Hostility Scoring**: Combines bot defense signals + sign-in likelihood. Score >= 40 forces Guided mode.
- **Automatic Override**: When Amazon is detected (hostility: 85), system automatically forces Guided Access, preventing headless blocking.

### 2. Behavioral Scanning & Network Monitoring
Instead of just grabbing the HTML, we "observe" the page and its traffic.
- **Stability Monitoring**: We wait for the node count to stop changing.
- **Mutation Tracking**: We measure how much the page "jitters" (high mutation = complex SPA).
- **Network Analysis**: We intercept Fetch/XHR/GraphQL calls to find backend API endpoints.
- **Bot Defense Scanner**: Proactively detects hostile signals (Akamai `_abck` cookies, DataDome scripts, perimeterx network calls).
- **Full Session Persistence (Storage State)**: ScrapeWizard captures the full `storage_state.json` (Cookies + LocalStorage + SessionStorage). This is critical for modern SPAs using JWTs or token-based auth hidden in the browser's storage.
- **Portability via Absolute Paths**: Generated scripts use `os.path.dirname(os.path.abspath(__file__))` to find their session files and output folders, meaning they run flawlessly from any directory or CI environment.

### 3. DOM Analysis 2.0 (Scoring & Filtering)
We don't just find all repeating classes. We score them based on "Richness" (how many child fields they have). This ensures we pick the main product list instead of the footer links.

### 4. Scraper Runtime Contract (SRC) & Hardening
This is the "Execution Protection" layer that ensures AI-generated code is robust and manageable across **Windows, macOS, and Linux**.
- **Dynamic Waiting**: The AI uses `smart_wait(selector)` which automatically handles hydration delays.
- **Infrastructure Isolation**: The AI never sees Playwright, storage files, or output logic. It only returns data dicts.
- **Robust Deduplication (Phase 6)**: Instead of assuming the first column is a unique ID, the runtime hashes the entire row content.
- **Structural Enforcement**: Repair and CodeGen agents are strictly instructed to preserve the execution block, preventing corrupted scripts during self-healing.
- **Unified Sink**: Data is automatically written to JSON, CSV, and Excel by the runtime based on user configuration.
- **OS Agnostic Paths**: All filesystem operations use `pathlib` and absolute path discovery, ensuring scripts run identically on any operating system.

### 5. UX Philosophy: The Firewall
"SRC owns HOW. Orchestrator owns WHEN. User owns WHAT."
By re-introducing decision gates, we ensure the user is always in the loop for high-value decisions (format, depth, quality) while the autonomous agents handle the low-value toil (selectors, waiting, I/O).
---

## 🚀 4. How to Learn from This
1.  **Read `orchestrator.py`**: This is the heart of the project. It connects all the pieces.
3.  **Break it**: Try a very complex site (like Amazon) to see how the **RepairAgent** handles anti-bot measures or complex lazy loading.

### 💡 Unified Guided Access (Earned Headless)
ScrapeWizard no longer just asks "Do you want to log in?". Instead, it recommends **Automatic (Headless)** for simple sites and **Guided Access** for complex ones (Amazon, LinkedIn). 
If you choose **Guided Access**, you can search, filter, and login manually. ScrapeWizard captures the *final* state (URL + Storage) and generates a scraper that works from that precise starting point.

---

## 🌉 5. The Bridge & Studio (MVP2)

To enable the transition to a visual IDE, we've implemented an architectural bridge.

### 1. Studio Backend (`studio/backend/main.py`)
A FastAPI server that acts as the orchestrator for the Desktop UI. 
- **CDP Bridge**: Proxies Chrome DevTools Protocol (CDP) events to the React frontend.
- **Session Management**: Tracks user recordings and state via `StudioState`.
- **Validation**: Uses Pydantic models in `studio/shared/validators.py` for strictly typed API requests.

### 2. Bridge Engine (`studio/bridge/engine.js`)
An injected script that transforms a standard browser page into an interactive picker.
- **Picker Mode**: Intercepts clicks and hovers to generate CSS selectors.
- **Box Model Overlay**: Draws real-time highlights over the target site to assist item selection.
- **Event Binding**: Communicates directly with the backend via `onElementSelected`.

### 3. AET (Abstract Extraction Template)
The visual alternative to the SRC. Instead of the AI guessing selectors from a DOM snapshot, the **AET compiler** builds extraction logic directly from the human-selected patterns in the Studio IDE.

---

> [!TIP]
> **Prompt Engineering Secret**: Notice how the prompts always end with "Start your response directly with 'import'". This prevents the LLM from writing "Sure! Here is the code..." which would break our Python execution.
