# 🛠️ ScrapeWizard — Detailed Implementation Plan

> [!NOTE]
> **ARCHIVED (2026-06-11)** — superseded by [PLATFORM_PLAN.md](PLATFORM_PLAN.md), the single
> source of truth. Kept for historical reference. The STEP 0 bugs catalogued below were fixed
> on 2026-06-11 (see PLATFORM_PLAN.md §14 for current status).

> Consolidated, step-by-step build plan from our full discussion.
> Companion to `ROADMAP.md` (strategy/vision). This file = **what to do, in order, with checks.**

**Locked decisions:**
- ✅ Offline (no-API) is the **default**; AI is an optional enhancer (`--ai` / key present).
- ✅ Selectors = **CSS + anchored XPath + fallback chain**, queried relative to the item container.
- ✅ **CLI-first.** No custom GUI in v1 — the headed browser + HTML report are the visual layer.
- ✅ Two products on one engine: **A) zero-config scraper**, **B) UI/UX tester**.

**Legend:** 🔴 critical bug · 🟢 feature · 🧹 cleanup · ✔️ acceptance check

---

## STEP 0 — Stop the bleeding (critical bugs first)  🔴
*Do these before anything else. The tool is likely broken on the main path today.*

### 0.1 🔴 `NameError`: `LLMClient` not imported in orchestrator
- **File:** `scrapewizard/core/orchestrator.py`
- **Problem:** Line 71 (`self.llm_client = LLMClient(...)`) runs in `__init__`, but `LLMClient`
  is only imported locally at line 854. Constructing `Orchestrator` → `NameError`.
- **Fix:** Add to the top imports: `from scrapewizard.llm.client import LLMClient`.
  Remove the redundant local import at line 854.
- ✔️ `scrapewizard build --url https://books.toscrape.com` gets past construction (run it).

### 0.2 🧹 Dead code in DOM analyzer
- **File:** `scrapewizard/recon/dom_analyzer.py:41-48`
- **Problem:** Code after `return` in `_is_rich_container` is unreachable.
- **Fix:** Delete lines 41-48 (or, if the recursive single-child case was intended, move it
  *before* the `return`). Decide intent, then make it reachable or remove.
- ✔️ `python -c "import ast,sys; ast.parse(open('scrapewizard/recon/dom_analyzer.py').read())"` clean; existing tests pass.

### 0.3 🧹 Duplicate `logs/` copy in bundling
- **File:** `scrapewizard/core/orchestrator.py:901-906` and `918-922`
- **Problem:** `_bundle_output` copies the `logs/` folder twice.
- **Fix:** Remove the second duplicated block (keep one).
- ✔️ Read the function; only one `copytree(logs_src, ...)` remains.

### 0.4 🧹 BeautifulSoup deprecation
- **File:** `scrapewizard/recon/dom_analyzer.py:116`
- **Problem:** `find_all(text=True)` is deprecated.
- **Fix:** Use `find_all(string=True)`.
- ✔️ No `DeprecationWarning` when running the analyzer on a sample page.

### 0.5 ✔️ Establish a baseline
- Run the existing golden test: `python tests/golden_sites/books.py` (note pass/fail).
- Run `scrapewizard doctor`.
- **Goal:** know what actually works *today* before adding features.

---

## MILESTONE 1 — The Shared Selector Engine (the keystone)  🟢
*Both products depend on this. Build it once, build it well.*

### 1.1 New module `scrapewizard/recon/selector_engine.py`
Input: a `DOMAnalyzer` item container + its candidate fields.
Output per field: a **ranked strategy list** anchored to the container.

```python
# Shape produced per field:
{
  "name": "price",
  "type": "price",                 # see 1.3
  "strategies": [                  # tried in priority order at runtime
    {"kind": "css",   "value": "[itemprop='price']"},
    {"kind": "css",   "value": "p.price_color"},
    {"kind": "xpath", "value": ".//*[contains(@class,'price')]"},
    {"kind": "xpath", "value": ".//div[2]/p[1]"}
  ]
}
```

**Strategy ladder (build in this priority):**
1. Stable attributes — `[itemprop]`, `[data-test*]`, `[data-*]`, `aria-label`, stable `id`
2. Semantic structure — `h2 > a`, `.price`, `img[src]`, role-based
3. Anchored relative XPath — `.//span[contains(@class,'title')]`
4. Positional XPath fallback — `.//div[2]/span[1]`

- ✔️ Unit test: feed a saved `books.toscrape.com` card → assert each field has ≥2 strategies
  and at least one XPath fallback.

### 1.2 🧹 Class-stability filter (upgrade `_is_safe_class`)
- **File:** `scrapewizard/recon/dom_analyzer.py`
- Reject machine-generated classes so we anchor on *meaningful* names:
  - CSS-in-JS hashes: `css-1a2b3c`, `sc-bdVaJa`, `jsx-1234567`
  - Tailwind/atomic: `mt-4`, `flex`, `text-sm`, `w-1/2`
  - Long random / digit-heavy tokens
- When no meaningful class exists → fall through to XPath (don't emit garbage CSS).
- ✔️ Unit test: `css-1x2y3z` and `mt-4` rejected; `price_color` accepted.

### 1.3 Field-type inference
- Replace generic `"text_field"` with: `price` (currency+digits), `rating` (★ / "x out of y"),
  `link` (`<a href>`), `image` (`<img src>`), `title` (largest heading-ish text), else `text`.
- ✔️ Unit test on a sample card: title/price/link/image named correctly.

### 1.4 Runtime resolver (try strategies in order)
- **File:** new helper in `scrapewizard_runtime/` (e.g. `resolver.py`).
```python
async def resolve(container, strategies):
    for s in strategies:
        loc = container.locator(s["value"]) if s["kind"] == "css" \
              else container.locator(f"xpath={s['value']}")
        if await loc.count():
            return (await loc.first.inner_text()).strip()
    return None
```
- ✔️ Unit test: when strategy #1 misses, #2/#3 still returns the value.

---

## MILESTONE 2 — Product A: Zero-Config Scraper (no API key)  🟢
*This is the star magnet. Ship it standalone.*

### 2.1 Deterministic "understanding" (replace the LLM when offline)
- Build `available_fields` directly from `selector_engine` output so the existing
  `USER_CONFIG` gate (`UI.ask_fields_*`) works unchanged.
- ✔️ With no API key, `analysis_snapshot.json` → field list with names + samples, no LLM call.

### 2.2 Template code generator `scrapewizard/codegen/template_codegen.py`
- Emits `generated_scraper.py` from the selector plan using a string/Jinja template.
- Must subclass the existing `BaseScraper` and honor the same contract
  (`navigate` / `get_items` / `parse_item`), calling the §1.4 resolver in `parse_item`.
- ✔️ Generated file imports, runs, and writes non-empty `data.json` on books.toscrape.com.

### 2.3 Orchestrator router (offline by default, AI optional)
- **File:** `scrapewizard/core/orchestrator.py`
- Add an `offline` flag (default **on** when no API key found; `--ai` forces LLM path).
- When offline: `RECON → (deterministic fields) → USER_CONFIG → (template codegen) → TEST → FINAL_RUN`,
  **skipping** `LLM_ANALYSIS`, LLM `CODEGEN`, and LLM `REPAIR`.
- Print: `"Running in offline mode (no API key needed) ✨"`.
- ✔️ `scrapewizard build --url https://books.toscrape.com` with **no key** → produces data.

### 2.4 Deterministic repair (no LLM)
- If a field is empty across all rows, advance it to the next strategy in its ladder and re-test.
- ✔️ Force a broken primary selector in a fixture → offline repair recovers via fallback.

### 2.5 🧹 Centralize `pagination_config`
- **File:** `scrapewizard/core/orchestrator.py` (built identically in 2+ places)
- Extract one helper `build_pagination_config(choice)`; call it everywhere.
- ✔️ One definition; grep shows a single constructor.

### 2.6 Offline golden tests
- Extend `tests/golden_sites/` to run the **offline** path (books, react_shop) with no key,
  asserting non-empty rows.
- ✔️ `pytest tests/golden_sites -k offline` green.

**🏁 M2 exit:** clone → `pip install` → `scrapewizard build --url ...` → CSV/JSON, **zero config.**

---

## MILESTONE 3 — Product B: UI/UX Tester (CLI, CI-native)  🟢
*Two commands sharing the M1 engine. No GUI.*

```
 record --url X  → recording.jsonl  → test recording.jsonl → report.html + exit 0/1
   (headed)         (editable)          (headless, in CI)
```

### 3.1 `scrapewizard record --url ...`
- Reuse `browser.start_interactive_recording()` + `recorded_events` + `recorder.py`.
- **Upgrade:** harden every recorded selector through the M1 Selector Engine (so a class
  rename doesn't break the test). Save to `recording.jsonl`.
- ✔️ Recording a click+type flow yields a `.jsonl` whose steps carry fallback selectors.

### 3.2 `scrapewizard test <recording.jsonl>` (replay + assert)
- Replay via existing `NavigationExecutor` (headless).
- After each step, collect: console errors, failed network requests (4xx/5xx — scanner
  already intercepts), and missing-selector failures.
- **Exit non-zero on any failure** (CI-native).
- ✔️ A flow with a deliberately broken step exits 1; a clean flow exits 0.

### 3.3 High-value checks
- **Visual regression:** screenshot per step (reuse `take_screenshot`); first run = baseline,
  later runs = pixelmatch diff; fail on > threshold.
- **Accessibility:** inject `axe-core` during replay; collect violations.
- ✔️ Changing a target page's color/layout flags a visual diff; an a11y issue is reported.

### 3.4 Report + CI
- Extend `scrapewizard/report/html_generator.py` → render pass/fail + screenshots + a11y +
  errors into `report.html`.
- Document a 6-line GitHub Actions snippet using `scrapewizard test`.
- ✔️ `report.html` opens and summarizes a run; CI job goes red on failure.

**🏁 M3 exit:** record a flow once, run `test` in CI, get a visual+a11y+functional report.

---

## MILESTONE 4 — Ease of Use & Adoption  🟢
*Turns "it works" into "people star it."*

- **4.1 `scrapewizard demo`** — no args, runs offline scraper on a safe public site, prints a
  result table. This is the README GIF.
- **4.2 `doctor` upgrade** — check Playwright browsers installed; print the exact fix command.
- **4.3 README rewrite** — lead with *"Works with zero API keys."* Badges, asciinema/GIF,
  3-line quickstart, **one Scrape example + one Test example.**
- **4.4 Friendly errors** — never dead-end; always suggest the next command.
- ✔️ A new user reaches first data/first report in < 60s without reading docs.

---

## MILESTONE 5 — Later (only if demand appears)
- Studio GUI (existing `studio/` React+Electron) as a thin front-end over the proven CLI.
- Recipe/plugin library for common sites.
- Docs site + examples gallery.

---

## Suggested order of work (fastest path to a demo)
1. **STEP 0** (unbreak the tool) — hours.
2. **M1** Selector Engine — the keystone.
3. **M2** offline scraper — *ship + demo here* (the star magnet).
4. **M4.1–4.3** demo + README — capture the win.
5. **M3** UI/UX tester — second pillar.
6. **M4.4 / M5** polish + optional GUI.

## Open questions (answer when convenient)
1. Test output: Python `pytest`+Playwright only, or also emit `.spec.ts`? *(Python-first recommended.)*
2. Does M2 ship alone first (recommended), or bundle the record→test MVP?
3. Branding: keep "ScrapeWizard," or umbrella as `scrape` + `test` subcommands?
