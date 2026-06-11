# 🖥️ ScrapeWizard — Admin Dashboard & Test Automation Plan

> [!NOTE]
> **ARCHIVED (2026-06-11)** — superseded by [PLATFORM_PLAN.md](PLATFORM_PLAN.md), the single
> source of truth. Kept for historical reference. The Part E critical bugs catalogued below
> were fixed on 2026-06-11 (see PLATFORM_PLAN.md §14 for current status).

> The product is a **local test-automation platform**: an **admin dashboard** where a user sees
> every test, its workflow, run history, and results. The deterministic engine (replay + checks)
> is the **backend worker** — the "sub part" that the dashboard drives. AI stays optional/bounded.

**Architecture (three layers):**
```
┌──────────────────────────────────────────────────────────────┐
│  ADMIN DASHBOARD (React/Vite frontend — studio/frontend)       │
│  Dashboard · Tests · Workflow view · Run history · Reports     │
└───────────────────────────┬──────────────────────────────────┘
                            │ REST + WebSocket (live runs)
┌───────────────────────────▼──────────────────────────────────┐
│  CONTROL API (FastAPI — studio/backend/main.py, extend)        │
│  CRUD tests · trigger runs · stream progress · settings        │
│  Storage: SQLite (tests, runs, results, screenshots)           │
└───────────────────────────┬──────────────────────────────────┘
                            │ imports as a library
┌───────────────────────────▼──────────────────────────────────┐
│  ENGINE = "the sub part" (deterministic, mostly exists)        │
│  Selector Engine · NavigationExecutor (replay) · Checks        │
│  (visual diff, a11y, console, network) · optional bounded AI   │
└──────────────────────────────────────────────────────────────┘
```

**What already exists vs. needs building:**
| Layer | Exists | To build |
|---|---|---|
| Engine | replay, recorder, scanner, screenshots, report | Selector Engine, checks (visual/a11y), AI budget |
| API | FastAPI scaffold, browser manager, CDP proxy | test CRUD, run trigger, SQLite, live WS |
| Dashboard | empty Vite scaffold + `index.css` | every screen (from scratch) |

---

## PART A — Data Model (the foundation)

New module `studio/backend/models.py` (Pydantic + SQLModel/SQLAlchemy → SQLite at `~/.scrapewizard/studio.db`).

```
TestCase     id, name, url, tags[], created_at, updated_at, suite_id?
TestStep     id, test_id, order, action(click/fill/wait/scroll/press/navigate),
             selector_strategies[] (CSS+XPath+fallback), value?, assertions[]
Assertion    id, step_id, kind(visible/text/url/a11y/visual/no_console_err), expected
Suite        id, name, description
TestRun      id, test_id|suite_id, status(queued/running/passed/failed),
             started_at, finished_at, duration_ms, ai_calls, ai_cost
StepResult   id, run_id, step_id, status, screenshot_path, visual_diff_score,
             console_errors[], network_errors[], a11y_violations[], healed_by_ai(bool)
Setting      key, value   (ai_mode, api_key_ref, base_url, visual_threshold…)
```

- ✔️ DB auto-creates on first run; `GET /health` reports DB ready.

---

## PART B — Control API (extend FastAPI)

Add to `studio/backend/` (split routers: `routes_tests.py`, `routes_runs.py`, `routes_settings.py`).

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/tests` | List all tests (+ last-run status badge) |
| `POST` | `/tests` | Create a test (from a recording `.jsonl` or manual) |
| `GET` | `/tests/{id}` | Test detail + ordered steps (**the workflow view**) |
| `PUT` | `/tests/{id}` | Edit name/steps/assertions |
| `DELETE` | `/tests/{id}` | Remove |
| `POST` | `/tests/{id}/record` | Open headed browser, capture flow → steps (reuse `start_interactive_recording`) |
| `POST` | `/tests/{id}/run` | Queue a run (background task) → returns `run_id` |
| `POST` | `/suites/{id}/run` | Run a whole suite |
| `GET` | `/runs?test_id=&status=` | Run history (filterable) |
| `GET` | `/runs/{id}` | Run detail: per-step results, screenshots, diffs, errors |
| `WS` | `/runs/{id}/live` | Live progress stream while running |
| `GET/PUT` | `/settings` | AI budget, thresholds, keys |

- The run executor is a thin wrapper that: loads the test → calls the engine's
  `NavigationExecutor` + checks per step → writes `StepResult` rows → emits WS progress.
- ✔️ `POST /tests/{id}/run` produces a `TestRun` row that moves queued→running→passed/failed,
  with one `StepResult` per step and a screenshot path each.

---

## PART C — The Engine (the deterministic "sub part")

This is Milestones 1–3 from `IMPLEMENTATION_PLAN.md`, exposed as importable functions the API calls.

1. **Selector Engine** (`scrapewizard/recon/selector_engine.py`) — CSS + anchored XPath +
   fallback chain, container-relative, stability-filtered. *(Shared with scraper.)*
2. **Replay** — existing `NavigationExecutor`, upgraded to resolve each step via the strategy
   ladder (try CSS → XPath → fallback).
3. **Checks per step (100% deterministic, no API):**
   - console errors · network 4xx/5xx (scanner already intercepts)
   - selector-resolved? (broken-element detection)
   - **visual regression** — screenshot vs. baseline (pixelmatch), `visual_diff_score`
   - **accessibility** — inject `axe-core`, collect violations
4. **Bounded AI layer (optional):**
   - `ai_mode = off` (default) → **zero calls**
   - `ai_mode = heal` → max **1 call** when the *entire* fallback chain fails, to re-locate
     the element by intent; mark `healed_by_ai=true`
   - `ai_mode = triage` → max **1 call** per failed run, to summarize *why* it failed
   - Every call logged with token cost (reuse `LLMClient` cost tracking) into the run.
- ✔️ A green run records `ai_calls = 0`. A broken-selector run in `heal` mode records ≤1 call and recovers.

---

## PART D — The Admin Dashboard (frontend, build from scratch)

Stack: keep Vite + React (already scaffolded). Add a router + a data layer (React Query) +
a component lib (e.g. shadcn/ui or Mantine). Build these screens:

### D1. Dashboard (home)
- Cards: total tests, pass rate (last 7d), runs today, avg duration, total AI cost.
- Recent runs list (status pills) + a small pass/fail trend chart.
- ✔️ Loads stats from `/tests` + `/runs`; empty-state guides to "Record your first test."

### D2. Tests list
- Table: name · URL · #steps · last run (✅/❌/—) · last run time · **Run** button.
- Actions: New (record), Edit, Delete, add to Suite, filter by tag/suite.
- ✔️ Clicking **Run** triggers `/tests/{id}/run` and navigates to the live run view.

### D3. Workflow view (test detail) — *the "see the workflow" screen you described*
- Vertical, ordered list of steps (click → fill → wait → assert…), each card showing:
  action, the resolved selector + its fallback chain, value, and attached assertions.
- Inline edit: reorder, edit selector/assertion, delete a step, add an assertion.
- ✔️ Editing a step persists via `PUT /tests/{id}` and re-runs cleanly.

### D4. Live run view
- Subscribes to `WS /runs/{id}/live`; shows each step turning green/red in real time,
  with the current screenshot.
- ✔️ Watching a run updates step-by-step without refresh; ends on passed/failed.

### D5. Run history + Report
- History table (filter by test/status/date).
- Run detail = per-step timeline + screenshot, **visual diff (before/after/diff)**,
  a11y violations list, console/network errors, AI heal/triage notes + cost.
- Reuse/extend `scrapewizard/report/html_generator.py` for an exportable HTML report.
- ✔️ A failed run clearly shows the failing step, its screenshot, and the reason.

### D6. Settings
- AI mode toggle (`off` / `heal` / `triage`), visual-diff threshold, API key entry
  (stored via existing keyring `security.py`), base URL.
- ✔️ Switching to `off` guarantees future runs make zero AI calls (visible in run metadata).

### D7. Suites & scheduling (later)
- Group tests into suites; run a suite; optional schedule (cron). Defer to a later milestone.

---

## PART E — Cleanup Plan (do alongside / before features)

### E0. Critical bugs (fix first — these break the app today) 🔴
| # | File:line | Bug | Fix |
|---|---|---|---|
| 1 | `core/orchestrator.py:71` | `LLMClient` used in `__init__`, only imported locally at L854 → `NameError` | Add top-level `from scrapewizard.llm.client import LLMClient`; drop local import |
| 2 | `studio/backend/main.py:190` | `except WebSocketDisconnect` but it's **never imported** → `NameError` on disconnect | `from fastapi import WebSocketDisconnect` |
| 3 | `studio/backend/main.py:85-99` | `browser_to_client()` is a dead placeholder (only sleeps) | Remove, or implement real CDP→client forwarding |

### E1. Dead / duplicate code 🧹
| # | File:line | Issue | Fix |
|---|---|---|---|
| 4 | `recon/dom_analyzer.py:41-48` | Unreachable code after `return` in `_is_rich_container` | Delete or restore intended recursion before the return |
| 5 | `core/orchestrator.py:901-906 & 918-922` | `_bundle_output` copies `logs/` twice | Remove duplicate block |
| 6 | `core/orchestrator.py` (×2+) | `pagination_config` built identically in multiple spots | Extract `build_pagination_config()` |

### E2. Deprecations / correctness 🧹
| # | File:line | Issue | Fix |
|---|---|---|---|
| 7 | `recon/dom_analyzer.py:116` | `find_all(text=True)` deprecated | `find_all(string=True)` |
| 8 | `studio/backend/main.py:167` | `run_coroutine_threadsafe(..., get_event_loop())` fragile | Capture loop once at startup; use a queue for WS fan-out |

### E3. Structural / quality 🧹
- Replace scrape-only `StudioProject`/`StudioState` (`studio/backend/state.py`) usage in the
  test flow with the new test models (Part A) — keep scrape models separate.
- Split `main.py` (200+ lines, mixed concerns) into routers + a `run_executor.py`.
- Add type hints + docstrings on new modules; remove `except:`/bare excepts (e.g. `main.py:197`).
- Tests: API contract tests (`tests/studio/`) for tests-CRUD + a fake run; engine unit tests
  from Milestone 1; one end-to-end "record → run → report" smoke test.

- ✔️ `pytest` green; `ruff`/`flake8` clean on touched files; app boots with no `NameError`.

---

## PART F — Build Order (sequenced)

1. **E0 critical bugs** — unbreak CLI + backend (hours).
2. **Engine M1 (Selector Engine)** + per-step **deterministic checks** — the worker.
3. **Part A (SQLite models)** + **Part B (tests CRUD + run trigger + run history)** — backend.
4. **Part D1–D5** dashboard screens (Dashboard, Tests, Workflow, Live run, Report) — the product.
5. **Part C bounded AI** (`off`/`heal`/`triage`) + **D6 Settings**.
6. **E1–E3 cleanup** folded in as modules are touched; finish with tests.
7. **D7 suites/scheduling** + Electron packaging (`studio/desktop`) — later.

**First demo-able milestone:** after step 4 — record a test, see its workflow, run it from the
dashboard, watch it go green/red live, open the report. Zero AI calls. That's the sellable core.

---

## Open questions
1. **Storage:** SQLite (recommended — real history/queries, still local & zero-setup) or flat JSON?
2. **Frontend kit:** shadcn/ui, Mantine, or plain CSS? (Affects build speed.)
3. **Packaging:** ship as a local web app (`uvicorn` + browser tab) first, or go straight to the
   Electron desktop shell in `studio/desktop`? *(Web-app-first recommended — simpler.)*
4. **Auth:** single local user (no login) for v1, or multi-user from the start? *(Single recommended.)*
