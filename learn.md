# 🎓 Learning ScrapeWizard: How it was Built

ScrapeWizard is an **Agentic Web Scraper Builder**. Unlike traditional scrapers where you write selectors manually, ScrapeWizard uses AI to understand the page structure, write the code, and even fix itself if the code fails.

This document breaks down the architecture, the logic, and the exact prompts used to build it.

---

## 🏗️ 1. Core Architecture

The project follows a **Modular State Machine** architecture. Each step of the process is isolated into a "Phase".

### The "Phase" Workflow (State Machine)
1.  **INIT**: User provides a URL.
2.  **LOGIN**: Manual login/navigation phase (optional).
3.  **RECON**: Playwright opens the site, performs a **Behavioral Scan** (stability, mutations, scroll dependency), and extracts a snapshot.
4.  **INTERACTIVE_SOLVE**: If a CAPTCHA is detected, the system pauses for manual human bypass and captures session cookies.
5.  **LLM_ANALYSIS**: AI looks at the DOM AND the Scan Profile to see if it's scrapable.
6.  **USER_CONFIG**: User selects fields (Title, Price, etc.) and confirms the **Adaptive Browser Mode**.
7.  **CODEGEN**: AI writes a standalone `generated_scraper.py` (with cookie-loading support).
8.  **TEST & REPAIR**: The script is automatically run. If it crashes (e.g. module error), the AI performs **Bulletproof Import** fixes.
9.  **FINAL_RUN**: The polished script runs and saves data (JSON, CSV, Excel).

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

### Agent B: The Coder (CodeGenerator)
**Goal**: Write a production-ready Playwright script.
**The "Stability First" Approach**: We strictly forbid the AI from using unique or transient IDs (like `id-t2_6l4z3`). Instead, it's instructed to find semantic, stable classes.

**The Prompt**:
```python
SYSTEM_PROMPT_CODEGEN = """
SELECTOR STABILITY RULES (CRITICAL):
1. NEVER use unique or transient IDs in selectors.
2. Prefer semantic classes and stable structural patterns (e.g., .author, .title).
3. Use the CSS SELECTORS from the analysis snapshot as a base.
"""
```

### Agent C: The Doctor (RepairAgent)
**Goal**: Fix the code if it fails.
**Context is King**: We give the agent the code, the exact traceback, and the user's feedback.

**The Prompt**:
```python
SYSTEM_PROMPT_REPAIR = """
You are a debugging expert. 
You will be given the original script, the error message, and the DOM context.
Return the COMPLETE corrected script. Start with an import statement.
"""
```

---

## 🛠️ 3. Technical Low-Level Details

### 1. Behavioral Scanning & Network Monitoring
Instead of just grabbing the HTML, we "observe" the page and its traffic.
- **Stability Monitoring**: We wait for the node count to stop changing.
- **Mutation Tracking**: We measure how much the page "jitters" (high mutation = complex SPA).
- **Network Analysis**: We intercept Fetch/XHR/GraphQL calls to find backend API endpoints.
- **Adaptive Browser Mode**: If we detect CAPTCHAs, Cloudflare, or low DOM health, we switch to **Headed mode** ("Headed mode is earned, not default").

### 2. Human-in-the-Loop (HITL) Solving
When a site blocks an automated agent, ScrapeWizard doesn't just fail. It enters the `INTERACTIVE_SOLVE` state:
- It opens a visible browser and pauses.
- The user solves the CAPTCHA or bypasses the blocker.
- **Session Persistence**: ScrapeWizard captures the resulting `cookies.json` and instructs the `CodeGenerator` to load them in the final scraper.

### 3. DOM Analysis 2.0 (Scoring & Filtering)
We don't just find all repeating classes. We score them based on "Richness" (how many child fields they have). This ensures we pick the main product list instead of the footer links.

### 4. Observability & Self-Healing
Every LLM call is logged to `llm_logs/`. 
- `codegen_response.py`: See what the AI originally wrote.
- `repair_response_X.py`: See how the AI tried to fix the error.
- **Bulletproof Imports**: We use a RegEx-based post-processor to automatically intercept and correct common import hallucinations (e.g., `async_playwright` module errors) before execution.
---

## 🚀 4. How to Learn from This
1.  **Read `orchestrator.py`**: This is the heart of the project. It connects all the pieces.
2.  **Experiment with Prompts**: Change `prompts.py` to see if the AI writes better or faster code.
3.  **Break it**: Try a very complex site (like Amazon) to see how the **RepairAgent** handles anti-bot measures or complex lazy loading.

---

> [!TIP]
> **Prompt Engineering Secret**: Notice how the prompts always end with "Start your response directly with 'import'". This prevents the LLM from writing "Sure! Here is the code..." which would break our Python execution.
