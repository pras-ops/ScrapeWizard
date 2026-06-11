# 🗺️ ScrapeWizard Roadmap — From AI Scraper to Zero-Config Web Automation Toolkit

> [!NOTE]
> **ARCHIVED (2026-06-11)** — superseded by [PLATFORM_PLAN.md](PLATFORM_PLAN.md), the single
> source of truth. Kept for historical reference. The code bugs catalogued in §6 were fixed
> on 2026-06-11 (see PLATFORM_PLAN.md §14 for current status).

> Goal: make ScrapeWizard a tool people **clone, run in 60 seconds, and star** — because it
> works with **no API key**, produces **robust selectors**, and does more than one thing.

---

## 0. The Big Idea (Positioning)

Today ScrapeWizard is "an AI scraper builder." That has two problems for adoption:
1. **It can't do anything without a paid LLM key** — most people bounce before seeing value.
2. **It does one thing** — scraping is crowded; "AI demo" tools rarely get starred.

The pivot: **one robust selector + automation engine, two products on top of it.**

```
                ┌─────────────────────────────────────────┐
                │        SHARED CORE (no API key)          │
                │  • Selector Engine (CSS+XPath+fallback)  │
                │  • Behavioral Scanner (stability/mutate) │
                │  • Recorder + NavigationExecutor (exists)│
                │  • Playwright Runtime (exists)           │
                └───────────────┬─────────────┬────────────┘
                                │             │
              ┌─────────────────▼──┐      ┌───▼─────────────────────┐
              │ PRODUCT A: SCRAPER │      │ PRODUCT B: UI/UX TESTER │
              │ data → CSV/JSON/XLS│      │ flows → Playwright tests │
              │                    │      │ + visual + a11y + checks │
              └────────────────────┘      └─────────────────────────┘
                          ▲ AI is OPTIONAL on both (enhancer, not gate)
```

**AI becomes an optional enhancer, not a wall.** No key → deterministic engine runs and
just works. Key present (or `--ai`) → AI improves field naming / fixes broken selectors.

---

## 1. Why this earns stars

| Lever | What we ship | Why it converts to stars |
|---|---|---|
| Zero-config | Works with **no API key** out of the box | Removes the #1 bounce point; "just works" demo |
| Robust selectors | CSS + anchored XPath + fallback chain | Scrapers/tests don't break next week |
| Two use-cases | Scraping **and** UI/UX test generation | Doubles the audience; novel combo |
| One-command demo | `scrapewizard demo` on a safe site | Instant "wow" in the README GIF |
| Clean code | Bugs fixed, typed, tested | Contributors trust it; people fork it |

---

## 2. SHARED CORE — The Selector Engine (foundation for everything)

This is the keystone. Both products depend on it. **Decision locked: CSS + XPath + fallback chain.**

### 2.1 New module: `scrapewizard/recon/selector_engine.py`
Takes `DOMAnalyzer` output and, for **each field**, produces a *ranked list of strategies*
that are **anchored to the item container** (queried relative to the card, not globally):

```python
{
  "name": "price",
  "type": "price",                 # inferred (price/title/link/image/rating/text)
  "strategies": [
    {"kind": "css",   "value": "[itemprop='price']"},        # 1. stable attribute
    {"kind": "css",   "value": "p.price_color"},             # 2. semantic class
    {"kind": "xpath", "value": ".//*[contains(@class,'price')]"}, # 3. anchored xpath
    {"kind": "xpath", "value": ".//div[2]/p[1]"}             # 4. positional fallback
  ]
}
```

**Strategy ladder (highest → lowest priority):**
1. **Stable attributes** — `[itemprop]`, `[data-test*]`, `[data-*]`, `aria-label`, stable `id`
2. **Semantic structure** — `h2 > a`, `.price`, `img[src]`, role-based
3. **Anchored XPath** — `.//span[contains(@class,'title')]` (relative to container `.`)
4. **Positional XPath fallback** — `.//div[2]/span[1]` (last resort)

### 2.2 Class-stability filtering (upgrade `_is_safe_class`)
Current check only validates the character set. Add rejection of machine-generated classes:
- CSS-in-JS hashes: `css-1a2b3c`, `sc-bdVaJa`, `jsx-1234567`
- Tailwind/atomic single-purpose: `mt-4`, `flex`, `text-sm`, `w-1/2`
- Long random hashes / numeric-heavy tokens

Anchor only on **meaningful, human-named** classes; fall through to XPath when none exist.

### 2.3 Field-type inference
Replace generic `"text_field"` names with inferred types via regex/heuristics:
- `price` → currency symbols + digits (`$`, `£`, `€`, `₹`)
- `rating` → "star", `★`, "x out of y", numeric ≤ 5 near "rating"
- `link` → `<a href>`, `image` → `<img src>`
- `title` → first/largest heading-ish text in the card

### 2.4 Runtime: "try strategies in order" helper
Add to `scrapewizard_runtime/` a resolver the generated code calls:
```python
async def resolve(container, strategies) -> str | None:
    for s in strategies:
        loc = container.locator(s["value"]) if s["kind"] == "css" \
              else container.locator(f"xpath={s['value']}")
        if await loc.count():
            return (await loc.first.inner_text()).strip()
    return None
```
This is what makes both scrapers **and** tests survive markup churn.

---

## 3. PRODUCT A — Zero-Config Scraper (carries over the earlier plan)

### Phase A1 — No-API deterministic pipeline
- `scrapewizard/codegen/template_codegen.py` — emits `generated_scraper.py` from the
  selector plan using a template (subclasses existing `BaseScraper`, same runtime contract).
- Deterministic `available_fields` built straight from `DOMAnalyzer`/`selector_engine`
  (replaces `UnderstandingAgent` when offline) so the `USER_CONFIG` gate still works.
- **Orchestrator router**: no API key found → offline path automatically; `--ai` or key
  present → existing LLM path. Skips `LLM_ANALYSIS`/`CODEGEN`/LLM-`REPAIR` when offline.
- Deterministic repair: when a field returns empty across all rows, drop to the next
  strategy in its ladder (no LLM needed for the common case).

### Phase A2 — Robustness (delivered mostly by §2)
- Container-relative extraction everywhere.
- Multi-strategy fallback wired into the template + runtime resolver.
- Golden tests (`tests/golden_sites/`) extended to run the **offline** path on
  `books.toscrape.com`, the React shop, etc., asserting non-empty rows with no key set.

---

## 4. PRODUCT B — UI/UX & Functional Testing (the new pillar)

You already have the hard parts. This wires them into a second output mode.

### What exists and gets reused
- `studio/bridge/recorder.py` — records events to `.jsonl` ✅
- `scrapewizard_runtime/navigation.py` — replays click/fill/wait/scroll/press ✅
- `studio/bridge/engine.js` — in-page element picker + box overlay ✅
- `recon/scanner.py` — stability/mutation/network behavioral signals ✅
- `browser.take_screenshot(...)` — already capturing `debug_recon.png` ✅

### Phase B1 — Record → Playwright test generation
- New command: `scrapewizard record --url ...` → drive a headed browser, capture the flow
  via the existing recorder, **anchor each step's selector through the Selector Engine**
  (so recorded tests don't break on a class rename).
- New emitter `scrapewizard/codegen/test_codegen.py` → outputs a runnable
  **`pytest` + Playwright** test file (and optionally a raw `.spec.ts`).
- Each recorded step becomes an assertion-friendly action with fallback selectors.

### Phase B2 — Assertions & checks (the "UX testing" value)
Turn a recording/scan into automatic checks:
- **Visual regression** — baseline screenshot per step; diff on re-run (pixelmatch-style).
- **Accessibility** — inject `axe-core` during replay, report violations.
- **Broken-element / dead-link scan** — flag missing selectors, 4xx/5xx requests
  (the scanner already intercepts network).
- **Performance/stability** — reuse mutation/stability metrics → flag layout jank, slow
  hydration, console errors.
- Output a single **`report.html`** (you already have `report/html_generator.py` +
  Jinja template to extend) summarizing pass/fail + screenshots + a11y + perf.

### Phase B3 — Assert mode in the CLI
- `scrapewizard test <recording.jsonl>` → replay + run all checks headless, exit non-zero
  on failure → **usable in CI**. This is what makes it a *real* tool, not a toy.

---

## 5. Ease of Use (Phase 3 from before, expanded)

- **`scrapewizard demo`** — one command, no args, runs the offline scraper on a safe public
  site and prints a result table. This is the README GIF.
- **Auto-detect no key** → friendly "Running in offline mode (no API key needed) ✨".
- **Preflight `doctor`** — already exists; extend to check Playwright browsers + give the
  exact fix command if missing.
- **README rewrite** — lead with *"Works with zero API keys"*, badges, asciinema/GIF,
  3-line quickstart, a "Scrape" example AND a "Test" example.
- Sensible defaults everywhere; never dead-end the user.

---

## 6. Code Cleanup (the "stuff you didn't mention")

Concrete issues found while reading the code:

| # | File / Location | Issue | Fix |
|---|---|---|---|
| 1 | `recon/dom_analyzer.py:41-48` | Unreachable dead code after `return` in `_is_rich_container` | Delete or restore intended recursion |
| 2 | `core/orchestrator.py:71` | `LLMClient(...)` used but **not imported at top** (only locally at L854) — likely `NameError` | Add top-level import; verify first |
| 3 | `core/orchestrator.py:901,918` | `_bundle_output` copies `logs/` folder **twice** | Remove the duplicate block |
| 4 | `recon/dom_analyzer.py:116` | `find_all(text=True)` — BS4 deprecation | Switch to `string=True` |
| 5 | `core/orchestrator.py` (×2+) | `pagination_config` built identically in multiple places | Extract one helper |
| 6 | repo-wide | Thin type hints / no docstrings in newer modules | Add as touched |
| 7 | `tests/` | No coverage for the offline path | Add offline golden tests (§3 A2) |

---

## 7. Suggested Sequencing (milestones)

**M1 — Core + Offline Scraper (the star magnet)**
- §2 Selector Engine (CSS+XPath+fallback, anchoring, stability filter, type inference)
- §3 A1 + A2 offline pipeline + router
- Cleanup #1, #2, #4 (the real bugs) pulled in early
- `scrapewizard demo` + README rewrite
- ➜ *Ship-able, demo-able, no key required.*

**M2 — UI/UX Tester**
- §4 B1 record → Playwright test gen
- §4 B2 visual + a11y + broken-element + perf checks
- §4 B3 CI-friendly `test` command
- Cleanup #3, #5, #6, #7

**M3 — Polish & growth**
- Studio (MVP2) integration of both products in the desktop UI
- Plugin/recipe library for common sites
- Docs site + examples gallery

---

## 8. Decisions

- **Offline vs AI:** ✅ *Auto-fallback default* — offline runs with no key; AI is an
  optional enhancer (`--ai` or key present). Keeps the existing LLM pipeline frozen/intact.
- **Selector strategy:** ✅ *CSS + anchored XPath + fallback chain.*
- **New: UI/UX testing pillar** ✅ added (Product B) reusing existing recorder/replay/scan.

---

## 9. Open questions for you

1. **Test output format** — `pytest+Playwright` (Python, matches your stack) or also emit
   Playwright `.spec.ts` for the JS crowd? (Python-first recommended.)
2. **Scope of M1** — ship offline scraper alone first, or bundle the `record→test` MVP too?
3. **Branding** — keep "ScrapeWizard," or umbrella both products under a broader name
   (e.g. "WebWizard") with `scrape` and `test` subcommands?
