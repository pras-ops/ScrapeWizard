# 🚀 Master Plan — AI-Powered UI/UX Test Automation Platform

> **The definitive, complete build plan.** Supersedes the testing sections of earlier docs;
> `ROADMAP.md` / `IMPLEMENTATION_PLAN.md` / `ADMIN_DASHBOARD_PLAN.md` remain as historical references.
>
> **Product in one sentence:** Record a workflow once → AI generates a production-ready test
> suite → a deterministic engine runs it forever → a multi-signal self-healing engine fixes
> breakage locally → AI is invoked **only** as last resort → everything managed from an admin
> portal with a built-in sandbox.

---

# PART I — STRATEGY

## 1. Market Position & Competition

The category (self-healing UI test automation) is real and growing — broken/flaky selectors
are consistently the #1 reported cost of UI automation. Competitive map:

| Competitor | What they are | Our edge over them |
|---|---|---|
| **Testim / mabl / Functionize** | Paid cloud SaaS, AI on every run | Local-first, data never leaves machine, **bounded AI cost**, no subscription, no lock-in |
| **Katalon** | Heavy commercial platform | Lightweight, Playwright-native, open |
| **Healenium** (closest free) | OSS self-healing for Selenium | Playwright-native, **richer signals** (geometry/visual/history/navigation), recording, portal |
| **Playwright `codegen`** (closest free recorder) | Free script recorder | They emit brittle one-shot scripts: no fingerprints, no healing, no portal, no history |
| **Emerging agentic-AI testers** | "AI drives the whole test" | Their model *requires* per-run AI cost; ours is deterministic-by-default — structurally cheaper and CI-predictable |

**Positioning sentence:** *"Self-healing UI test automation that runs locally — deterministic
by default, AI only when a test actually breaks. Predictable cost, no cloud, no lock-in."*

**Strategic rule:** the moat is **fingerprint-based local healing** (M1+M4). Do not compete on
enterprise feature breadth (RBAC/scheduling/drag-drop) until the moat ships and has users.

## 2. Measured Baseline (updated 2026-06-11 after fixes, verified by execution)

| Layer | Status | Evidence |
|---|---|---|
| Main `build` path | ✅ **Fixed 2026-06-11** | `LLMClient` now imported at top of `core/orchestrator.py`; `Orchestrator` constructs cleanly (verified by construction test) |
| Fresh install | ✅ **Fixed 2026-06-11** | `yaspin>=2.0.0` added to `requirements.txt` and `pyproject.toml` |
| Unit tests | ✅ 25/25 pass | Includes construction guard test (`tests/core/test_orchestrator_construction.py`); fresh-install CI matrix added (`.github/workflows/ci.yml`) — ladder rungs 1–2 done |
| Studio backend | ✅ **Fixed 2026-06-11** | `WebSocketDisconnect` imported; dead `browser_to_client`/`forward_event` removed; bare `except` narrowed; localhost bind + CORS locked |
| Studio frontend | ⚠️ Empty | Only `index.css`; zero components — portal is 100% to-build |
| Syntax | ✅ Clean | All `.py` files compile; BS4 deprecation warning eliminated |
| Reusable assets | ✅ | Recorder, replay (`NavigationExecutor`), behavioral scanner + network interception, screenshots, HTML report generator, multi-provider `LLMClient` with token/cost tracking, FastAPI scaffold + CDP screencast proxy, keyring security |

## 3. Risk Register & Mitigations

| # | Risk | Severity | Mitigation (built into the plan) |
|---|---|---|---|
| R1 | **Healing mis-matches** — too-loose scoring heals to the *wrong element*, silently corrupting tests (worse than failing) | High | Mutation fixture suite (§9.4) tuned *before* release; confidence thresholds; "healed" results flagged for user approve/reject; never auto-persist a heal without a passing re-run |
| R2 | **Recording fidelity** — shadow DOM, iframes, canvas, virtualized lists break naive capture | High | Detect-and-declare: recorder identifies unsupported constructs and tells the user explicitly (no mysterious failures). Shadow-DOM piercing in v1.1; canvas out of scope |
| R3 | **Scope explosion** — portal Wave 2 (drag-drop, RBAC, scheduling) is months of non-differentiating work | High | Hard milestone gate: Wave 2 starts only after Wave 1 has real usage. §16 "what NOT to build" |
| R4 | **Agentic-AI competitors** commoditize recording | Medium | Lean into the cost/privacy counter-position; bounded-AI guarantee is provable in run metadata |
| R5 | **Solo-maintainer surface area** | Medium | SQLite not Postgres; local web app not Electron-first; pytest export so users aren't locked to the platform |
| R6 | **Flaky target apps** cause false reds | Medium | Per-step retry with smart waits (exists: `smart_wait`); quarantine status for known-flaky tests |

## 4. Success Metrics (how we know it works)

- **TTFD (time to first demo):** new user goes record → run → green report in **< 5 minutes**.
- **Healing efficacy:** ≥80% of single-mutation breakages (class rename, container move, text tweak) heal at tiers 0–5 with **zero AI calls** on the fixture suite.
- **Healing safety:** 0 wrong-element heals above the acceptance threshold on the fixture suite.
- **Cost guarantee:** green run = $0.00 AI, displayed per-run in the portal.
- **Adoption proxy:** GitHub stars / clones after README+demo ship (M3).

---

# PART II — PRODUCT SPECIFICATION

## 5. AI Usage Policy (the economic core)

AI appears at exactly **two moments**, both bounded, both logged:

| Moment | What AI does | Budget |
|---|---|---|
| **Creation** (once per test) | Understands recorded flow; names test/steps; suggests assertions; groups reusable components; flags edge cases | 1–2 calls per test, ever |
| **Last-resort recovery** (tier 6) | Only after the entire healing ladder fails: analyze failure, propose new locator, regenerate step | ≤1 call per broken element, verified by re-run |

- `ai_mode = off` → **zero** calls ever (template generation, healing stops at tier 5).
- `ai_mode = creation` → AI at creation only.
- `ai_mode = full` → creation + tier-6 recovery.
- Every call logged: provider, model, tokens, cost (reuse `LLMClient` tracking) → surfaced
  per test and per run in the portal. **The guarantee is provable, not marketing.**
- AI receives **compact fingerprints, never raw HTML dumps** → tiny token counts.

## 6. Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│ ADMIN PORTAL (React + Vite — studio/frontend, from scratch)         │
│ Dashboard · Tests · Step Manager · Flow Designer (Wave 2)           │
│ Live Monitoring · Run History · Reports · Settings · Team (Wave 2)  │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ REST + WebSocket
┌──────────────────────────────▼─────────────────────────────────────┐
│ CONTROL API (FastAPI — studio/backend, extend)                      │
│ routers: tests · runs · suites · components · environments ·        │
│ schedules · settings  |  run queue + worker dispatch                │
│ Storage: SQLite (~/.scrapewizard/studio.db) + artifact dir          │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ imports as a library
┌─────────────┬────────────────▼──────────────┬──────────────────────┐
│ RECORDER     │ SANDBOX RUNNER                │ SELF-HEALING ENGINE  │
│ headed       │ isolated Playwright contexts, │ tiers 0–5 local      │
│ browser +    │ worker pool, per-step checks  │ (zero API),          │
│ fingerprint  │ (visual/a11y/console/network),│ tier 6 = AI          │
│ capture      │ artifacts, live WS stream     │ last resort          │
└─────────────┴───────────────┬───────────────┴──────────────────────┘
                              │ creation-time + tier-6 only
                       ┌──────▼──────┐
                       │  AI LAYER   │ multi-provider LLMClient (exists)
                       └─────────────┘
```

**Module layout (new code — `engine/` does not exist yet; created in M1):**
```
engine/
  fingerprint.py        # capture + serialize element fingerprints
  selector_engine.py    # CSS+XPath ladder builder, stability filter
  healing.py            # tier 0–6 resolution ladder + scoring
  test_generator.py     # flow.json → internal steps + pytest export
  sandbox.py            # isolated runner, worker pool, artifacts
  checks/
    visual.py           # screenshot baseline + pixelmatch diff
    a11y.py             # axe-core injection + violation collection
    console_network.py  # console errors, 4xx/5xx capture
studio/backend/
  models.py             # SQLModel tables (§12)
  routes_*.py           # routers per resource (§13)
  run_executor.py       # queue → sandbox → DB writes → WS events
studio/frontend/src/    # portal screens (§11)
```

## 7. Element Fingerprint (the foundational data structure)

Self-healing with parent/sibling/position/history signals is only possible if **all signals
are captured at record time**. Captured for every element a step touches:

```jsonc
{
  "selectors": [                        // ranked ladder, §8
    {"kind":"css","value":"[data-test='checkout']","rank":1},
    {"kind":"css","value":"button.btn-primary","rank":2},
    {"kind":"xpath","value":".//button[contains(.,'Checkout')]","rank":3},
    {"kind":"xpath","value":".//div[3]/button[1]","rank":4}
  ],
  "tag": "button",
  "attributes": {"id":"co-btn","class":"btn btn-primary","type":"submit",
                 "data_attrs":{"data-test":"checkout"},"aria":{"label":"Checkout"}},
  "text": "Checkout",                   // normalized inner text
  "context": {
    "parent":    {"tag":"div","classes":["cart-footer"],"text_head":"Total:"},
    "siblings":  [{"tag":"a","text":"Continue shopping","offset":-1}],
    "ancestors": ["div.cart-footer","section#cart","main"],
    "child_count": 1,
    "index_in_parent": 2
  },
  "geometry": {"x":912,"y":640,"w":160,"h":44,"viewport":[1280,720],
               "x_pct":0.71,"y_pct":0.89},          // viewport-normalized
  "visual": {"crop":"artifacts/fp_017.png",          // small screenshot crop
             "dom_neighborhood_hash":"a3f9c2…"},     // hash of surrounding DOM
  "navigation": {"page_url":"/cart","came_from":"/products","leads_to":"/checkout"},
  "history": [                                       // appended on every heal/resolve
    {"ts":"…","resolved_by":"tier0","selector":"[data-test='checkout']"}
  ]
}
```

**Capture implementation:** injected recorder script walks the DOM at event time
(`getBoundingClientRect`, attribute scrape, parent/sibling walk), backend takes the
screenshot crop. Stored per `TestStep` (§12). Size budget: ≤5 KB/fingerprint + crop image.

## 8. Selector Engine

`engine/selector_engine.py` — builds each fingerprint's ladder, container/context-relative:

1. **Stable attributes:** `[data-test]`/`[data-testid]`/`[data-*]`, `[itemprop]`,
   `aria-label`, stable `id` (reject auto-generated ids: digit-heavy, UUID-like)
2. **Semantic structure:** meaningful classes (`button.checkout`), tag+text (`role`/text engines)
3. **Anchored relative XPath:** `.//button[contains(.,'Checkout')]`
4. **Positional XPath fallback:** `.//div[3]/button[1]`

**Class-stability filter** (extends `_is_safe_class`): reject CSS-in-JS hashes
(`css-1a2b3c`, `sc-…`, `jsx-…`), Tailwind/atomic utilities (`mt-4`, `flex`, `text-sm`),
digit-heavy/random tokens. If nothing meaningful remains → skip to XPath (never emit garbage CSS).

✔️ Unit-tested on saved HTML fixtures: ≥2 strategies + ≥1 XPath per element;
hashed classes rejected, semantic classes kept.

## 9. Self-Healing Engine (the moat)

`engine/healing.py` — deterministic ladder per element per step. **Tiers 0–5: zero API calls.**

| Tier | Signal | Resolution method |
|---|---|---|
| 0 | Primary selector | Direct hit → done (the normal, free case) |
| 1 | Selector ladder | Remaining CSS/XPath strategies in rank order |
| 2 | Attributes + text | Page-wide search: same tag, scored on attribute overlap + normalized-text similarity |
| 3 | **Structure** | Find remembered parent/ancestors (their own mini-fingerprints) → search within; confirm via sibling signature + `index_in_parent` |
| 4 | **Geometry + visual** | Candidates near recorded `x_pct/y_pct`; compare `dom_neighborhood_hash`; optional crop similarity |
| 5 | **History + navigation** | What did this element resolve to in past runs? Verify page context (`came_from`/`leads_to`/URL) matches before trusting |
| 6 | **AI (last resort)** | Compact fingerprint + trimmed DOM region → propose locator → **verified by re-running the step** before acceptance |

### 9.1 Scoring & safety
- Each tier emits `(candidate, confidence)`; accept ≥ threshold (initial: 0.85, tunable),
  else fall to next tier.
- Multiple candidates above threshold within a tier → ambiguous → **do not heal**, fail with
  an "ambiguous match" report (prevents wrong-element corruption — risk R1).
- A heal is only persisted after the step **re-runs successfully** with the new locator.

### 9.2 Learning loop
Every successful resolution appends to `fingerprint.history`; the selector ladder re-ranks
(promote what worked). Tests get **more stable over time** — this is the "historical element
mappings" requirement, and it compounds into a durable advantage.

### 9.3 Transparency & control
Each heal recorded as a `HealEvent` (tier, old→new locator, confidence, screenshot).
Portal shows a "healed" badge per step; user approves (persist) or rejects (revert + mark
for review). Settings: auto-accept threshold vs. always-ask.

### 9.4 Tuning methodology (answers risk R1 — this is where iteration time goes)
Build `tests/healing_fixtures/`: a small local demo app + scripted **mutations**:
1. class renamed · 2. id removed · 3. element moved to new container · 4. text reworded ·
5. sibling inserted · 6. attribute changed · 7. element removed (must reach tier 6 / fail cleanly)

CI asserts per mutation: expected tier resolves it, confidence ≥ threshold, and **zero
wrong-element matches**. Thresholds are tuned against this suite before any release.

## 10. Recorder, Generation & Sandbox

### 10.1 Recorder (extends existing `start_interactive_recording` + `engine.js`)
- Headed browser; user performs the flow; every event captured with full fingerprint (§7).
- Overlay (existing `engine.js` box-model highlight) shows what was captured per action.
- Auto-inserted assertions: page transition → URL assertion; element appear → visibility wait.
- **Unsupported constructs detected and declared** (R2): iframe/shadow-DOM/canvas warnings
  at record time, not mysterious replay failures. Shadow-DOM piercing: v1.1.
- Output: `flow.json` (ordered steps: action, value, fingerprint).
- ✔️ 5-step flow yields 5 steps each carrying selectors, context, geometry, crop, navigation.

### 10.2 Test generation (`engine/test_generator.py`)
- **AI mode:** one structured call with compact step list → names, extra assertions,
  component grouping, edge-case suggestions.
- **Template mode (`ai_mode=off`):** deterministic naming + standard assertions. Fully usable.
- Outputs: (a) internal runnable steps in DB; (b) **exported standalone pytest+Playwright
  file** including the healing resolver — runs in any CI without the platform (anti-lock-in,
  R5). `.spec.ts` export deferred.
- ✔️ Recorded login flow → named steps + assertions + exported pytest file passes standalone.

### 10.3 Sandbox runner (`engine/sandbox.py`)
- Isolated Playwright context per run (fresh profile); worker pool (configurable N).
- Per-step: healing-aware resolution → action → checks:
  visual diff vs baseline (pixelmatch, threshold setting) · a11y (`axe-core`) ·
  console errors · network 4xx/5xx (scanner interception exists).
- Artifacts per step: screenshot, optional video/trace; stored under the run's artifact dir.
- Timeouts: per-step + global; retry-with-smart-wait before failing (R6).
- Environment injection: base URL + credentials/variables from the selected Environment (§12).
- Live progress events → WS → portal monitoring view. Exit status drives run status.
- ✔️ Generated test runs with live step status and a complete artifact trail, no user setup
  (bootstrap runs `playwright install` via extended `doctor`).

## 11. Admin Portal (two hard-gated waves)

Stack: existing Vite+React scaffold + React Router + React Query + shadcn/ui (default; see §17).

### Wave 1 — Manage & Run (the sellable core)
| # | Screen | Contents | Acceptance |
|---|---|---|---|
| 1 | **Dashboard** | totals, pass rate (7d), runs today, avg duration, AI spend, recent runs, trend chart | loads from API; empty-state → "Record your first test" |
| 2 | **Tests list** | search/filter/tags, last-run badge, Run/Edit/Delete/New-recording | Run → triggers run, navigates to live view |
| 3 | **Test detail / Step Manager** | ordered step cards: action, locator + full ladder, value, assertions, heal history; inline edit/reorder/delete | edits persist and re-run cleanly |
| 4 | **Live monitoring** | WS-driven step-by-step green/red with current screenshot | updates without refresh; terminal state shown |
| 5 | **Run history + report** | filterable history; run detail: per-step timeline, visual before/after/diff, a11y violations, console/network errors, heal events, AI cost; HTML export (extend existing generator) | failing step + reason obvious at a glance |
| 6 | **Settings** | `ai_mode` (off/creation/full), provider keys (keyring), visual threshold, heal auto-accept threshold, parallelism | `off` provably → 0 calls in run metadata |

### Wave 2 — Low-code & Enterprise (gated on Wave 1 usage)
7. **Visual Flow Designer** — drag-drop palette of actions/assertions over the same step
   model; "capture element" button opens recorder for one element. *(UI sugar over §12 — built last for a reason.)*
8. **Component library** — save step groups ("Login") as reusable components; reference in
   many tests; update once → propagate.
9. **Environments** — dev/stage/prod: base URL, credentials, variables; chosen at run time.
10. **Scheduling & orchestration** — cron per suite, queue, notifications (webhook first).
11. **Team & access control** — local users, roles (admin/editor/viewer). SSO: not until demanded.

---

# PART III — ENGINEERING REFERENCE

## 12. Data Model (SQLite via SQLModel — `studio/backend/models.py`)

```
TestCase     id, name, url, tags[], suite_id?, created_at, updated_at,
             generated_by(ai|template), exported_path?
TestStep     id, test_id, order, action(navigate|click|fill|press|scroll|wait|assert),
             value?, fingerprint(JSON §7), component_id?
Assertion    id, step_id, kind(visible|text|url|attr|a11y|visual|no_console_err), expected
Component    id, name, description          # reusable step group (Wave 2)
ComponentStep id, component_id, order, action, value?, fingerprint
Suite        id, name, description
TestRun      id, test_id|suite_id, env_id?, status(queued|running|passed|failed|error),
             started_at, finished_at, duration_ms, ai_calls, ai_cost_usd, trigger(manual|schedule|api)
StepResult   id, run_id, step_id, status, duration_ms, screenshot_path,
             visual_diff_score?, console_errors[], network_errors[], a11y_violations[],
             healed(bool), heal_event_id?
HealEvent    id, run_id, step_id, tier(0-6), old_locator, new_locator, confidence,
             approved(bool?), created_at
Environment  id, name, base_url, variables(JSON), secret_refs[]   # secrets in keyring
Schedule     id, suite_id, cron, enabled, last_run_at             # Wave 2
User         id, name, role(admin|editor|viewer)                  # Wave 2; v1 = implicit admin
Setting      key, value    # ai_mode, thresholds, parallelism, provider config
```
Artifacts (screenshots/video/crops) on disk under `~/.scrapewizard/artifacts/{run_id}/`,
paths in DB. ✔️ DB auto-creates on first boot; `GET /health` reports schema version.

## 13. API Surface (FastAPI routers)

```
Tests        GET/POST /tests · GET/PUT/DELETE /tests/{id}
             POST /tests/{id}/record      # open headed browser, capture → steps
             POST /tests/{id}/generate    # (re)generate names/assertions (AI or template)
             POST /tests/{id}/export      # standalone pytest file
             POST /tests/{id}/run         # → run_id (queued)
Suites       CRUD /suites · POST /suites/{id}/run
Runs         GET /runs?test_id=&status=&from=&to= · GET /runs/{id}
             GET /runs/{id}/artifacts/{step} · WS /runs/{id}/live
Heals        GET /heals?test_id= · POST /heals/{id}/approve · POST /heals/{id}/reject
Components   CRUD /components                        (Wave 2)
Environments CRUD /environments
Schedules    CRUD /schedules                         (Wave 2)
Settings     GET/PUT /settings
Meta         GET /health · GET /stats (dashboard aggregates)
```
Conventions: Pydantic request/response models (extend `studio/shared/validators.py`);
no bare excepts; run executor is a background worker consuming a queue table.

## 14. Cleanup & Hardening (all verified)

### 14.1 Critical — fix first (M0) 🔴 — **ALL FIXED 2026-06-11, verified by execution**
| # | Location | Bug | Status |
|---|---|---|---|
| 1 | `requirements.txt` | `yaspin` missing (used `utils/ux.py:3`) — fresh installs crash | ✅ fixed — added to requirements.txt + pyproject.toml |
| 2 | `core/orchestrator.py` | `LLMClient` used in `__init__`, imported only locally → `NameError`, `build` dead for everyone | ✅ fixed — top-level import; construction verified |
| 3 | `studio/backend/main.py` | `except WebSocketDisconnect` — never imported → `NameError` on disconnect | ✅ fixed — added to fastapi import |

### 14.2 Dead/duplicate code 🧹 — **ALL FIXED 2026-06-11**
| # | Location | Issue | Status |
|---|---|---|---|
| 4 | `studio/backend/main.py` | `browser_to_client()` dead placeholder (sleep loop) | ✅ removed (was never called) |
| 5 | `recon/dom_analyzer.py` | unreachable code after `return` in `_is_rich_container` | ✅ removed |
| 6 | `core/orchestrator.py` | `_bundle_output` copied `logs/` twice | ✅ duplicate block removed |
| 7 | `core/orchestrator.py` | duplicated `pagination_config` construction ×3 | ✅ extracted `_build_pagination_config()` helper |

### 14.3 Deprecations/correctness 🧹 — **ALL FIXED 2026-06-11**
| # | Location | Issue | Status |
|---|---|---|---|
| 8 | `recon/dom_analyzer.py` | BS4 `text=` deprecated → `string=` | ✅ fixed — pytest warning gone |
| 9 | `studio/backend/main.py` | fragile `run_coroutine_threadsafe(..., get_event_loop())` | ✅ fixed — dead `forward_event()` removed entirely |
| 10 | `studio/backend/main.py` | bare `except:` | ✅ narrowed to `except Exception:` |

### 14.4 Verification ladder (keeps it working forever)
1. **Construction test** — build `Orchestrator` with temp project (catches bug-#2 class). *Would have caught today's breakage.*
2. **Fresh-install CI job** — clean venv → `pip install -r requirements.txt` → `--help` (catches #1).
3. **Engine unit tests** — fingerprint capture, selector engine, healing tiers on HTML fixtures (offline, fast).
4. **Healing mutation suite** (§9.4) — efficacy + safety gates in CI.
5. **Golden E2E** — record→generate→run on the bundled demo app, asserted in CI.
6. **Self-test** — platform runs a recorded test against its own portal each release.

## 15. Milestones, Effort & Exit Criteria

| Milestone | Contents | Effort* | Exit criterion |
|---|---|---|---|
| **M0 — Unbreak** | Cleanup #1-#3, #8 + ladder rungs 1-2 in CI | hours | fresh clone runs `build`; CI guards both bugs |
| **M1 — Engine core** | Fingerprints (§7) + Selector Engine (§8) + recorder upgrade (§10.1) + demo app for fixtures | 1-2 wks | recorded flow carries full fingerprints; unit tests green |
| **M2 — Generate & run** | Template generation (§10.2) + minimal sandbox (§10.3: replay, checks, exit status, artifacts) | 1-2 wks | record → generated test → sandbox run passes with report data |
| **M3 — Portal Wave 1** | Models (§12) + API (§13) + screens 1-6 (§11) | 2-4 wks | manage/run/monitor/report in browser — **first demo & sellable core**; ship README+GIF here |
| **M4 — Self-healing** | Tiers 0-5 (§9) + mutation suite (§9.4) + heal history/badges | 2-3 wks | ≥80% single-mutation heal rate, 0 wrong-element matches, 0 AI calls |
| **M5 — AI layer** | Creation-time generation + tier-6 recovery + cost surfacing (§5) | 1 wk | bounded calls provable in run metadata |
| **M6 — Portal Wave 2** | Designer, components, environments, scheduling, RBAC | gated | no-code creation + nightly suites — **only after Wave 1 usage** |

\* solo-dev, focused; calibrate after M1.
Order rationale: healing (M4) before AI (M5) so "minimal AI" is true from the first
healing release; portal Wave 1 (M3) early because the dashboard *is* what users evaluate;
M3 before M4 so feedback arrives while the moat is being built.

## 16. Scope Discipline — what NOT to build (until proven needed)
- ❌ Electron packaging (web app + uvicorn first; `studio/desktop` waits)
- ❌ Postgres / multi-tenant server (SQLite is enough for local-first)
- ❌ SSO, audit logs, granular permissions (role enum only, Wave 2)
- ❌ `.spec.ts` export (pytest first)
- ❌ Canvas-app support; shadow-DOM piercing deferred to v1.1 (declared, not silent)
- ❌ Cloud execution / hosted SaaS (the local-first stance *is* the differentiation)

## 17. Open Decisions
1. **Component lib:** shadcn/ui (default) vs Mantine — pick at M3 start, affects velocity only.
2. **Demo app:** bundle a tiny local web app (recommended — enables offline demo + healing
   fixtures §9.4 + golden E2E rung 5 with one artifact) vs rely on public sites.
3. **Run queue:** in-process asyncio queue (recommended for v1) vs separate worker process.
4. **Heal auto-accept:** default ON above 0.95 confidence, or always-ask? (Suggest: always-ask
   in v1, learn from approvals.)
5. **Product name:** see §18 — decide before M3 (renaming after launch is far more expensive).

---

# PART IV — COMPLETE PRODUCT & LAUNCH

*Everything beyond code that a launchable product needs. Most of this was not explicitly
requested — it's included because shipping without it is what makes "done" projects fail.*

## 18. Product Identity & Branding

**The name problem (decide before M3):** "ScrapeWizard" describes the *old* product. A test
automation platform named after scraping confuses buyers, hurts search, and triggers
compliance allergies ("scraping" reads as grey-area in enterprise). Options:
- **Rename the product** (recommended) — e.g. a testing-flavored name; keep `scrapewizard`
  internals temporarily, rename packages gradually. Check: PyPI availability, GitHub org,
  domain, npm (for any JS packages), trademark conflicts (basic search).
- **Umbrella brand** — one engine, two named products (scraper + tester) under a neutral brand.
- **Keep the name** — only viable if scraping remains the headline (it no longer is).

**Identity kit (1–2 days, don't over-invest):** logo (simple wordmark is fine), color pair,
social preview image (GitHub OpenGraph), 1-line tagline = positioning sentence (§1),
consistent naming in CLI prompt, portal header, docs, README.

## 19. Portal UI/UX Design Spec (our own product's UX)

The portal *is* the product impression. A testing tool with a sloppy UI loses trust instantly
— the UI must demonstrate the quality bar it claims to enforce.

### 19.1 Design system
- One component library (shadcn/ui default) + tokens: 2 font sizes for body/heading, 4/8px
  spacing grid, one accent color, semantic colors (pass=green, fail=red, healed=amber,
  running=blue pulse, queued=gray).
- **Dark mode from day one** (developers; trivial with tokens, painful to retrofit).
- Information hierarchy rule: every screen answers one question first —
  Dashboard: "is everything green?" · Test detail: "what does this test do?" ·
  Run detail: "why did it fail?" The answer must be visible without scrolling.

### 19.2 The states most tools forget (each screen ships with all four)
| State | Requirement |
|---|---|
| **Empty** | Every list/dashboard has a designed empty state with one CTA ("Record your first test"). Never a blank table. |
| **Loading** | Skeletons (not spinners) for lists; progress narration for long ops ("Launching browser…", "Installing Chromium ~120 MB, one-time"). |
| **Error** | Human sentence + what to do next + "copy details" for bug reports. No raw tracebacks in the UI (full trace goes to the log file). |
| **Partial** | Run with 3/10 steps done renders cleanly; mid-run refresh recovers state from the API. |

### 19.3 Key flows (design before building, even as paper sketches)
1. **First-run** → §20 onboarding.
2. **Record** — portal: name + URL → headed browser opens with overlay → floating step
   counter widget ("4 steps captured · ⏹ finish") → finish → land **directly in Step Manager**
   with steps visible (instant payoff, no dead-end).
3. **Run & watch** — Run button → live view auto-opens → steps turn green sequentially →
   terminal banner (passed/failed) → failed: one click to the failing step's evidence
   (screenshot + diff + console).
4. **Heal review** — amber badge on healed step → side-by-side old/new locator + screenshot →
   Approve / Reject buttons → approval updates fingerprint history.
5. **Failure triage** — run detail leads with the *first* failing step, its screenshot,
   and the reason classified (selector-not-found / assertion-failed / timeout / crash).

### 19.4 Accessibility & ergonomics of our own UI
- We ship an a11y *checker* — our portal must pass axe-core itself (CI rung: run our own
  a11y check on the portal; eat our own dog food, great marketing line too).
- Keyboard: `r` run, `/` search, `Esc` close panels. Focus states everywhere.
- Responsive down to laptop (1280px); mobile = read-only dashboards (nice-to-have, defer).

## 20. First-Run Experience & Onboarding

The < 5-minute TTFD metric (§4) is won or lost here.

1. **Install:** `pip install <product>` → `<product> start` → browser opens portal. One command.
2. **Bootstrap check (auto):** on first start, detect missing Playwright browsers → offer
   one-click install with size warning; detect port conflicts → auto-pick next port.
3. **Welcome screen:** two buttons — **"Try the demo"** (runs a bundled test against the
   bundled demo app §17.2 — instant green run, zero setup, zero network) and
   **"Record your first test"** (the §19.3 record flow against the user's own URL).
4. **Inline education:** first heal event → one-time explainer popover ("This step self-healed.
   Here's what that means…"). First AI call → cost popover. No upfront tutorial walls.
5. **No login** in v1 (single local user) — nothing between install and value.

## 21. Packaging, Distribution & Updates

- **Distribution:** PyPI package; `pipx install` documented as preferred. Frontend ships
  **pre-built** inside the wheel (no Node required for users) — CI builds Vite bundle into
  package data; FastAPI serves static files.
- **One entry point:** `<product> start` (runs API + serves portal + opens browser).
  Subcommands: `doctor`, `record`, `run`, `export`, `demo`.
- **Versioning:** SemVer; DB schema versioned with migrations (Alembic or hand-rolled
  `schema_version` + idempotent upgrade scripts — SQLite-friendly).
- **Update path:** `pip install -U` + on-boot migration; portal shows "update available"
  (checks PyPI JSON, respects offline/opt-out).
- **Supported platforms:** Windows + macOS + Linux from day one (Playwright covers all;
  CI matrix must too — you develop on Windows, most users will be on macOS/Linux).
- **Existing `release.yml`:** extend, don't replace (§26).

## 22. Documentation & Demo Assets (docs are part of the product)

| Asset | Contents | When |
|---|---|---|
| **README** | tagline, 30–60s GIF of record→fail→self-heal→green, 3-line quickstart, feature grid, bounded-AI cost table, comparison vs Healenium/codegen | M3 (launch gate) |
| **Quickstart** | install → demo → first real test, < 1 page | M3 |
| **User guide** | recording, step editing, assertions, healing (what each tier means, approving heals), AI modes & costs, environments, CI usage of exported pytest | M3–M4, grows |
| **Troubleshooting** | top 10 failures with fixes (browser install, ports, auth walls, iframes/shadow DOM limits) | M3 |
| **Demo video** | 2–3 min: record → break the page → watch it self-heal | launch week |
| **Architecture doc for contributors** | this file, maintained | ongoing |
| Site | start with GitHub README + Pages; real docs site only post-traction | post-launch |

**The money shot** (build deliberately, it's the whole pitch in 10 seconds): demo app test
passes → rename a CSS class in the demo app → re-run → step heals (amber) → suite green →
"0 AI calls, $0.00". Script this as both the README GIF and the launch video centerpiece.

## 23. Software Quality Standards (cross-cutting)

- **Error handling policy:** every user-facing error = (what happened, why probably, what to
  do next). Engine raises typed exceptions (`SelectorNotFound`, `HealAmbiguous`,
  `BrowserMissing`…) → API maps to structured error responses → portal renders humanely.
  Ban bare `except:` (lint rule; two already flagged in §14).
- **Logging:** structured logs (existing `pythonjsonlogger`) to `~/.scrapewizard/logs/` with
  rotation; `--verbose` for console; per-run engine log attached to run artifacts.
- **Crash & telemetry (opt-in only, privacy-first):** first-run prompt, default **off**,
  anonymous counts only (runs, heal-tier frequencies, error classes — never URLs, selectors,
  or page content). Heal-tier stats directly tune §9.4. Local-first product → privacy story
  must be airtight; document exactly what is sent.
- **Performance budgets:** portal loads < 2s; fingerprint capture adds < 50ms/action while
  recording; a 10-step test replays in roughly page-speed time (no artificial sleeps —
  replace `navigation.py`'s fixed 1s waits with condition-based waiting).
- **Code standards:** `ruff` + format on CI; type hints on all new modules; PR template with
  the verification ladder as checklist.

## 24. Security & Privacy Hardening

| Area | Action |
|---|---|
| **Local API exposure** | ✅ Partially fixed 2026-06-11: now binds `127.0.0.1`, CORS restricted to portal dev origins. Remaining for M3: per-session token the portal sends with each request 🔴 |
| Secrets | All credentials/API keys via keyring (`utils/security.py` exists); never in DB or logs; environment "secret_refs" resolve at runtime only |
| Artifact hygiene | Screenshots may contain user data — stored locally only, retention setting ("keep last N runs"), one-click purge |
| Recorded credentials | Recorder must **mask** values typed into `input[type=password]` (store placeholder, re-inject from env/keyring at run time) — easy to forget, embarrassing to leak |
| Dependencies | `pip-audit` + `npm audit` in CI; pin versions; Dependabot |
| Generated code | Exported pytest files contain only locators/assertions — no secrets baked in |
| Disclosure | `SECURITY.md` with contact for vulnerability reports |

## 25. Licensing & Legal

- **License:** MIT (already) — right call for adoption; revisit only if open-core (§28).
- **Third-party:** axe-core (MPL 2.0 — fine to invoke, don't fork), Playwright (Apache 2.0),
  pixelmatch (ISC) — include a `THIRD_PARTY_LICENSES` file generated in CI.
- **Privacy statement:** one honest page — what's stored (everything local), what's sent
  (nothing, unless opt-in telemetry → exact field list), AI calls (sent to *user's own*
  configured provider, under their key).
- **Responsible-use note:** docs state the tool is for testing sites you own/have authority
  over; recorder respects auth walls (no bypass features).

## 26. Release Engineering (CI/CD)

**CI pipeline (PR-blocking), extends existing `release.yml`:**
1. Lint + typecheck (`ruff`, `mypy` on new modules) · 2. Unit tests (engine, API) ·
3. **Construction test** (§14.4 r1) · 4. **Fresh-install matrix** — Win/macOS/Linux ·
5. Healing mutation suite (M4+) with efficacy/safety gates ·
6. Golden E2E vs bundled demo app · 7. Frontend build + portal self-a11y check ·
8. `pip-audit`/`npm audit`.

**Release flow:** tag → CI builds wheel (frontend bundled) → publish PyPI → GitHub Release
with autogenerated changelog (Conventional Commits). **Beta channel:** `pip install --pre`
for early adopters (§27).

**Release checklist (every release):** ladder green on 3 OSes · demo flow manually verified
once · CHANGELOG · docs updated for changed features · migration tested against a
previous-version DB.

## 27. Support, Community & Feedback Loop

- GitHub: issue templates (bug w/ "copy details" payload from §19.2, feature, healing-miss
  report — the most valuable one: a healing-miss report with fingerprint attached is tuning
  data), Discussions on, public roadmap (this doc distilled into a GitHub Project).
- In-product: "Report a problem" on every failed run → pre-filled issue with sanitized
  diagnostics (user reviews before sending).
- **Beta program before public launch:** 5–15 real users from testing communities (r/QualityAssurance,
  Ministry of Testing, testing Discords). Their feedback gates the public launch (§29).
- Response discipline post-launch: first-48h issues answered fast — early responsiveness
  compounds into contributors.

## 28. Monetization (decide later, design for it now)

v1 is free OSS — adoption is the asset. Viable later paths, in order of fit:
1. **Open-core:** engine + portal Wave 1 free forever; Wave 2 enterprise (RBAC, SSO,
   scheduling at scale, audit) paid. The milestone gating already matches this split.
2. **Hosted runner** (optional cloud execution for teams) — contradicts local-first pitch
   least if *additive*.
3. **Support/services.**
Avoid: metering the AI layer (it runs on the user's own key — that's the differentiator).
No paywall before there's traction; just keep the Wave 1/Wave 2 boundary clean.

## 29. The Complete Step-by-Step Path to Launch

**Stage 0 — Unbreak & guard (M0)** *(hours)*
1. Fix `yaspin` requirement, `LLMClient` import, `WebSocketDisconnect` import (§14.1).
2. Add construction test + fresh-install CI (§14.4 r1–r2). Everything verified green.

**Stage 1 — Foundation (M1)** *(~1–2 wks)*
3. Decide product name (§18) — blocks branding, PyPI, README.
4. Build bundled demo app (doubles as healing fixtures + golden E2E target).
5. Fingerprint capture + Selector Engine + recorder upgrade, unit-tested.

**Stage 2 — Engine runs (M2)** *(~1–2 wks)*
6. Template test generation + pytest export.
7. Minimal sandbox: replay + checks + artifacts + exit status.
8. Golden E2E in CI: record→generate→run on demo app.

**Stage 3 — The product appears (M3)** *(~2–4 wks)*
9. DB models + API routers + run executor.
10. **Security fixes:** localhost bind, CORS, session token, password masking (§24). 🔴
11. Portal Wave 1 screens with all four UI states (§19.2); dark mode; design tokens.
12. Onboarding: `start` command, bootstrap checks, welcome screen, "Try the demo" (§20).
13. Packaging: wheel with built frontend; `pipx` path verified on all 3 OSes (§21).
14. README + quickstart + troubleshooting + GIF (§22).
15. **→ Beta release** (`--pre` on PyPI) to 5–15 recruited testers (§27).

**Stage 4 — The moat (M4)** *(~2–3 wks, overlaps beta feedback)*
16. Healing tiers 0–5 + mutation suite + thresholds tuned to §4 gates.
17. Heal review UX (badges, approve/reject) + heal history.
18. The "money shot" demo flow scripted (§22).

**Stage 5 — AI layer (M5)** *(~1 wk)*
19. Creation-time generation, tier-6 recovery, per-run cost surfacing, `ai_mode` settings.
20. Verify bounded-cost guarantee end-to-end (metadata shows 0 calls on green runs).

**Stage 6 — LAUNCH** *(1 wk of prep)*
21. Pre-launch checklist (§30) fully green.
22. Demo video recorded; README GIF final; landing = polished README (+ GitHub Pages).
23. Launch posts: Show HN, r/QualityAssurance + r/softwaretesting, Ministry of Testing,
    testing newsletters, X/LinkedIn. Lead with the money shot, not the feature list.
24. 48-hour response watch on issues/comments.

**Stage 7 — Post-launch**
25. Triage feedback → tune healing with real-world misses → fix top frictions.
26. Start Wave 2 (M6) **only if** users ask for those features specifically.
27. Revisit monetization (§28) once there's organic usage.

## 30. Pre-Launch Checklist (the gate — all must be true)

- [ ] Fresh `pipx install` → `start` → demo green, on Windows, macOS, Linux
- [ ] TTFD < 5 min for a first-time user (test with someone who's never seen it)
- [ ] Healing gates met: ≥80% mutation-suite efficacy, 0 wrong-element heals, 0 AI calls
- [ ] Green run provably $0.00; `ai_mode=off` provably zero calls
- [ ] API bound to localhost; CORS locked; passwords masked in recordings
- [ ] Every portal screen has empty/loading/error/partial states; portal passes its own a11y check
- [ ] README + GIF + quickstart + troubleshooting done; demo video uploaded
- [ ] LICENSE, THIRD_PARTY_LICENSES, SECURITY.md, privacy statement in repo
- [ ] Issue templates + "report a problem" flow working
- [ ] Versioned DB schema + tested upgrade from previous beta
- [ ] CI ladder fully green; release pipeline produces installable wheel
- [ ] Beta feedback incorporated or consciously deferred (logged in issues)
