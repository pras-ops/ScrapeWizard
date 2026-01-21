# 🎓 Learning ScrapeWizard: How it was Built

ScrapeWizard is an **Agentic Web Scraper Builder**. Unlike traditional scrapers where you write selectors manually, ScrapeWizard uses AI to understand the page structure, write the code, and even fix itself if the code fails.

This document breaks down the architecture, the logic, and the exact prompts used to build it.

---

## 🏗️ 1. Core Architecture

The project follows a **Modular State Machine** architecture. Each step of the process is isolated into a "Phase".

### The "Phase" Workflow (State Machine)
1.  **INIT**: User provides a URL.
2.  **RECON**: Playwright opens the site, takes a screenshot, and extracts a "minified" DOM.
3.  **LLM_ANALYSIS**: AI looks at the DOM to see if it's scrapable.
4.  **USER_CONFIG**: User selects fields (Title, Price, etc.) via CLI.
5.  **CODEGEN**: AI writes a standalone `generated_scraper.py`.
6.  **TEST & REPAIR**: The script is automatically run. If it crashes, the AI reads the error and fixes the code.
7.  **FINAL_RUN**: The polished script runs and saves data (JSON, CSV, Excel).

---

## 🧠 2. The "Brains" (LLM Agents)

We used three specialized "Agents" instead of one giant prompt. This makes the system more reliable.

### Agent A: The Analyst (UnderstandingAgent)
**Goal**: Look at thousands of lines of HTML and find the "interesting" parts.
**How it works**: We don't send raw HTML (it's too big). We use `BeautifulSoup` to find repeating classes and tags, then send a structured JSON "Snapshot" to the LLM.

**The Prompt**:
```python
SYSTEM_PROMPT_UNDERSTANDING = """
You are an expert web scraping analyst. 
Analyze the provided JSON snapshot of a webpage's DOM structure.
Determine if and how it can be scraped.
Output a JSON object: scraping_possible, confidence, reason, available_fields, pagination.
"""
```

### Agent B: The Coder (CodeGenerator)
**Goal**: Write a production-ready Playwright script.
**Challenge**: LLMs sometimes hallucinate imports or add markdown explanations like "Here is your code:".
**Solution**: We use strict rules and a post-processing `_extract_python_code` function to clean the output.

**The Prompt**:
```python
SYSTEM_PROMPT_CODEGEN = """
You are an expert Python Playwright developer.
1. Output ONLY valid Python code - NO explanations.
2. Use asyncio and async_playwright.
3. Use the CSS SELECTORS from the analysis snapshot.
4. ALWAYS save data to 'output/data.json' for testing.
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

### 1. Handling "Async in Sync"
Playwright is asynchronous, but Command Line Interfaces (CLI) work best in a synchronous loop.
**Solution**: We use `asyncio.run(some_async_func())` inside the Orchestrator's synchronous methods to bridge the two worlds.

### 2. DOM Redaction (Fitting in the AI's Window)
Sending a full `html` page is expensive and often exceeds the AI's "context window".
**The Trick**: In `dom_analyzer.py`, we strip out:
- `<script>` and `<style>` tags.
- SVG paths.
- Comments.
- Large blocks of irrelevant text.
We only keep the structure and class names.

### 3. Self-Healing Loop
When a script is generated, we run it in a `subprocess`.
- If `exit_code != 0`, we capture `stderr`.
- We classify the error (e.g., `selector_not_found`, `timeout`, `syntax_error`).
- We feed this back to the **RepairAgent**.
- The AI "sees" the failure and tries a different CSS selector.

---

## 🚀 4. How to Learn from This
1.  **Read `orchestrator.py`**: This is the heart of the project. It connects all the pieces.
2.  **Experiment with Prompts**: Change `prompts.py` to see if the AI writes better or faster code.
3.  **Break it**: Try a very complex site (like Amazon) to see how the **RepairAgent** handles anti-bot measures or complex lazy loading.

---

> [!TIP]
> **Prompt Engineering Secret**: Notice how the prompts always end with "Start your response directly with 'import'". This prevents the LLM from writing "Sure! Here is the code..." which would break our Python execution.
