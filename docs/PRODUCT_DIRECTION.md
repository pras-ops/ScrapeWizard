# 🧭 Product Direction — One Engine for Flows: Test, Extract, Monitor

> Follows [PRODUCT_WORKFLOW_ANALYSIS.md](PRODUCT_WORKFLOW_ANALYSIS.md) and
> [COMPETITIVE_RESEARCH.md](COMPETITIVE_RESEARCH.md). This document records the decisions made
> and designs the product around them.

## 0. Decisions (from the founder)

| Question | Decision |
|---|---|
| Scraper's role | **It is the base engine.** Scraping and testing do the same work |
| Target market | **Small firms and projects that need testing but can't staff QA**, and want all their user flows managed in one space, not isolated individual tests |
| Primary user | **The "user tester"**: whoever does the testing (founder, PM, developer, support person), not a QA specialist |
| Sharing | **Shareable reports** |
| Code | **Needed sometimes**, because code gives control that replaying steps can't |

---

## 1. Why the scraper is the right base engine

Scraping and testing are the same pipeline with a different last step:

```
                 NAVIGATE → LOCATE → ACT → EXTRACT → ┬─ EXPORT  = scraping
                                                     ├─ ASSERT  = testing
                                                     └─ ALERT   = monitoring
```

A test is a scraper that asserts. A scraper is a test that exports. A monitor is a test on a timer.

**Evidence from the code:** the scraper side already has the page-understanding capabilities the
tester lacks.

| Capability | Scraper side (exists) | Tester side (today) |
|---|---|---|
| Network intelligence | `Scanner`: API endpoint discovery (`/api/`, GraphQL, JSON), JSON response status, WebSocket detection (`recon/scanner.py:182-222`) | Logs responses ≥ 400 only |
| Stability / waiting | `Runtime.smart_wait`, `wait_for_idle`, mutation and stability tracking | Fixed sleeps |
| Structured data | `DOMAnalyzer`: repeating-section detection, field detection | None |
| Pagination | `PaginationDetector`, runtime pagination loop | None |
| Sessions / auth | Guided access, `storage_state` capture and reuse | Password masked, can't replay |
| Actions | Navigation steps: click, fill, wait, scroll, press | `navigate`, `click`, `fill` only |
| Resilience | — | Selector ladder, fingerprints, healing tiers (tester is ahead here) |

So the plan isn't "fold the scraper into the tester." It's **merge both into one flow engine**:
the scraper supplies page understanding, and the tester supplies fingerprints and healing.

---

## 2. Why code is needed (and why replay-only tools fail)

Replay-only tools (Codegen, mabl, Testim, Selenium IDE) repeat a **fixed path**. Research puts
the no-code ceiling at roughly **85–90% of cases**. The remaining 10–15% are exactly the cases
that catch real bugs:

| Real scenario | Why step-replay fails | What it needs |
|---|---|---|
| "Add the **cheapest in-stock** item to the cart" | The target changes every run | **Extract a list → pick by rule** |
| "Price on the product page = price in cart = checkout total" | Replay clicks but never compares | **Extract to a variable → assert later** |
| "Every row in the orders table has a valid date and status" | Can't loop | **For each extracted item → assert** |
| "Search results are sorted by price across **all pages**" | Stops at page 1 | **Pagination loop + extraction** |
| "Cookie banner *may* appear" / A/B variants | Fails on the optional step | **Condition: if visible → act** |
| "Sign up with a **new unique email** each run" | Replays the same email, then "already exists" | **Generated data / variables** |
| "Create the test user via **API**, then test the UI" | UI setup is slow and flaky | **API call step** |
| "Order total = Σ items + tax" | Business rule | **Computed assertion / code** |
| "After *Pay*, `POST /api/orders` returns 201 with an `orderId`" | Doesn't see the network | **Wait-for-response + JSON assertion** |

Most of these need **extraction plus variables plus logic**, which is scraper territory. That's
why the scraper-as-core idea is right, and it's a genuine competitive edge: other test tools
treat data extraction as an afterthought.

### How to add code without Katalon's trap

Katalon's dual "Manual view ↔ Script view" converts code back and forth. The conversion is lossy:
code gets rewritten or lost when you switch, and users are told to never switch views. **Don't
build two-way conversion.** Use a layered step model instead:

| Layer | For | What it is |
|---|---|---|
| **1. Recorded steps** | Everyone | Click, fill, select, press… captured by doing the task |
| **2. Smart steps** (still visual) | The user tester | Extract, Assert, Condition, Loop, Paginate, API call, Wait-for-response, Data/variables. Configured with forms, no code |
| **3. Code step** | When forms aren't enough | A **self-contained code block inside the flow**, with a documented context (`page`, `vars`, `extract()`, `expect()`, `request`). Shown as one card in the visual flow and edited in a code editor. **Never converted back into visual steps** |
| **Eject** | Teams that outgrow it | **One-way** export of the whole flow to a Playwright project (pytest or TS). The exit door, which removes lock-in fear |

The flow (a list of typed steps) is always the source of truth. Code blocks are just one step type
inside it, so nothing is ever lossy.

---

## 3. The product for small firms: "all your user flows in one space"

A small firm doesn't want "a test." It wants to know **whether signup, login, search, checkout
and billing still work**, without hiring anyone.

### 3.1 Flow Map (the home screen)
A board of the app's **journeys** (Signup, Login, Search, Checkout, Password reset…), each with
live health across every dimension: functional ✅, network ⚠️, a11y ❌, performance ✅, visual ✅.
**Shared steps** such as "Login" are reusable **components**: record once, reused by every flow,
healed once. This is the "whole-flow view instead of individual tests" the target market wants.

### 3.2 Runs happen without a QA person
- **On demand:** "Run all flows" before a release.
- **Scheduled monitoring:** every hour or night, locally, or in CI via the CLI. Small firms pay
  Checkly $24–64+/month plus per-run fees for exactly this; locally it costs nothing per run.
- **Alerts:** email, Slack or webhook when a flow breaks, with the report link attached.

### 3.3 One run, every dimension, one issue list
As designed in the workflow analysis: capture everything (actions, HAR, console, trace), replay
once, evaluate every check pack, and output **deduplicated findings** with status
(new / known / accepted / fixed).

### 3.4 Shareable reports (Jam-style)
- **Single-file HTML report**: self-contained with embedded screenshots and findings. Email it,
  attach it to a ticket, or host it anywhere (GitHub Pages, S3). Works with no server.
- **Per-finding link**: a direct anchor to one issue, with its evidence (screenshot, failing
  request, console line, trace step).
- **Optional later:** a hosted share service (possible paid tier; see §6).
- ⚠️ **Redaction is mandatory:** HAR files and console logs contain auth tokens, cookies and
  personal data. Scrub `Authorization`, `Cookie`, `Set-Cookie`, tokens in URLs and bodies, and
  masked form values **before** anything is exported or shared.

---

## 4. Why this beats the competition

| | Playwright Codegen / Agents | mabl / Testim | Katalon | Checkly | Jam | **This product** |
|---|---|---|---|---|---|---|
| Start with no code | ⚠️ records to code | ✅ | ✅ | ❌ code | ✅ capture | ✅ record |
| Data extraction + variables + logic | code only | limited / JS | ✅ (dev-heavy) | code only | ❌ | ✅ **native smart steps (scraper core)** |
| Code when needed, without lossy conversion | code-only | bolted-on JS | ❌ lossy dual view | code-only | ❌ | ✅ **code step + one-way eject** |
| All dimensions in one run (UI/API/a11y/visual/perf) | UI | partial | partial | UI/API | capture only | ✅ |
| Flow map / whole-app view | ❌ | ⚠️ | ⚠️ | ⚠️ | ❌ | ✅ |
| Scheduled monitoring + alerts | ❌ | ✅ (paid) | ✅ (paid) | ✅ per-run fees | ❌ | ✅ **local, no per-run cost** |
| Shareable reports | HTML report | cloud | cloud | cloud | ✅ | ✅ single-file + per-finding link |
| Safe self-healing | Healer (LLM, edits code) | ✅ (black box) | ✅ | ❌ | ❌ | ✅ **deterministic, refuses rather than guesses, audited** |
| Cost for a small firm | free (needs devs) | ~$450–500+/mo | enterprise pricing | $24–64+/mo + runs | freemium | **free/local; optional paid sharing** |
| Lock-in | none | high | high (Testsigma similar) | medium | n/a | **none (eject to Playwright)** |

**Positioning:**
> *"Record your app's user flows once. Check they work (clicks, data, APIs, accessibility,
> speed) on every release or every hour. Share one clear report. Drop into code when you need
> control. No QA team, no per-run bill, no lock-in."*

---

## 5. Target architecture — one flow engine, three modes

```
                         ┌──────────────── FLOW (source of truth) ─────────────────┐
                         │ typed steps: recorded · smart (extract/assert/if/loop/   │
                         │ paginate/api/wait-response/data) · code · component-ref  │
                         └───────────────────────────┬──────────────────────────────┘
                                                     │
  ┌──────────────────────────── CORE ENGINE (merged scraper + tester) ─────────────────────────┐
  │ Session     Runtime (browser/context), storage_state auth, env + secrets                    │
  │ Locate      selector ladder (role-first) + fingerprints + safe healing                      │
  │ Act         click/fill/select/press/upload/hover/scroll                                     │
  │ Extract     DOMAnalyzer (repeating lists, fields) → typed values/tables → variables         │
  │ Paginate    PaginationDetector + loop                                                       │
  │ Observe     network (Scanner → full HAR + API catalog), console, trace, screenshots         │
  │ Stabilize   smart_wait / wait_for_idle / mutation tracking (replaces fixed sleeps)          │
  │ Code        sandboxed code-step context: page, vars, extract(), expect(), request           │
  └────────────────────────────────────────────┬────────────────────────────────────────────────┘
                  ┌─────────────────────────────┼──────────────────────────────┐
             TEST mode                     EXTRACT mode                   MONITOR mode
        check packs → findings        export CSV/XLSX/JSON           schedule → run → alert
        (functional, network/API,     (today's scraper output)       (email/Slack/webhook)
         a11y, visual, perf, console)
                  └─────────────────────────────┼──────────────────────────────┘
                                  REPORTS (single-file HTML, per-finding links, JUnit)
                                  STUDIO (flow map, recorder, findings inbox, heal review)
```

### Where today's code goes

| Today | Becomes |
|---|---|
| `scrapewizard_runtime/` (Runtime, BaseScraper, NavigationExecutor) | Core **Session / Act / Stabilize**; `BaseScraper`'s `get_items` / `parse_item` becomes an Extract step, and pagination becomes a Paginate step |
| `recon/scanner.py` | Core **Observe**, extended from endpoint discovery to full HAR + API catalog |
| `recon/dom_analyzer.py`, `pagination.py` | Core **Extract / Paginate**, also powering "suggest assertions" |
| `engine/selector_engine.py`, `fingerprint.py`, `healing.py` | Core **Locate** (make role-first) |
| `engine/recorder.py` | Recorder on the core, plus capture of network/console/trace and more events |
| `engine/sandbox.py`, `checks/` | **Test mode** runner + check packs, rebuilt as a flow executor |
| `core/orchestrator.py` (scraper state machine) | **Retired over time**; its guided-access and assessment logic moves into core Session |
| `llm/understanding`, `codegen`, `repair` | **Optional AI assists**: propose extractions/assertions, write a code step from plain English ("check total = sum of items"), tier-6 heal. Always logged, never on the hot path |
| CLI `build` | `extract` mode (keep the command as an alias for compatibility) |
| Studio | Flow map, recorder, flow editor (visual + code step), findings inbox, reports, schedules |

---

## 6. Business model fit (small firms)

- **Free / open-source core:** local engine, Studio, recorder, all check packs, scheduling via
  CLI, single-file reports. This drives adoption.
- **Optional paid convenience** (later, only if there's traction):
  - hosted share links for reports and findings
  - hosted scheduled runs, for small firms without an always-on machine or CI
  - team workspace
  - alerts/integrations hub

  This matches the open-core idea in PLATFORM_PLAN §28 and never meters the local engine.

---

## 7. Roadmap (replaces the order in earlier plans)

| Phase | Deliverable | Why first |
|---|---|---|
| **0. Flow schema** | A versioned JSON schema of step types (recorded, smart, code, component-ref) plus the variables model | **The contract everything builds on**: recorder writes it, engine runs it, Studio edits it, eject exports it |
| **1. Merge the engines** | One core package (Session / Locate / Act / Extract / Paginate / Observe / Stabilize); flow executor runs today's 3 actions + Extract + Assert + variables | Removes the two-products problem at the code level |
| **2. Smart steps** | Extract (value/list/table), Assert (compare, count, regex, sum), Condition, Loop, Paginate, API call, Wait-for-response, Data (generated / CSV) | Delivers the "control beyond replay" promise without code |
| **3. Code step + eject** | Code block with context API + editor; one-way export to a Playwright project | The escape hatch; kills lock-in fear |
| **4. Capture + findings** | Recorder captures HAR/console/trace, role-first locators, `storage_state` auth; findings dedup; check packs incl. network/API + performance | From the workflow analysis, phases 1–4 |
| **5. Flow map + components + monitoring** | Journey board, reusable components (Login), schedules, alerts | The small-firm value: all flows in one space, running without a QA person |
| **6. Shareable reports** | Single-file HTML, per-finding anchors, **redaction** | The chosen sharing model |
| **7. Review-first Studio UX** | Proposals after recording, findings inbox, heal review; engineer panel as "advanced" | Built for the user tester |

Frontend polish from MARKET_READY_PLAN (React Query, primitives, TS strict) happens **inside
Phase 5–7**, on the new screens, rather than polishing the current per-step screens.

---

## 8. Risks

1. **Scope.** This is a big product. Guard it: Phases 0–3 plus a minimal Phase 4 (HAR + findings)
   is already a strong, differentiated v1. Performance, visual polish and hosted sharing can follow.
2. **Code-step safety.** Code runs locally, which is fine for your own flows. Shared or imported
   flows containing code must show a clear warning before running.
3. **Secrets in shared reports.** Redaction must be on by default, tested, and impossible to
   forget (§3.4).
4. **The engine merge is a refactor with regression risk.** Keep the existing CLI `build` and the
   `test` path working through Phase 1, and gate it with the existing golden tests plus new
   flow-executor tests.
5. **Naming.** "ScrapeWizard" undersells a flow-quality product. Decide before any public launch
   (PLATFORM_PLAN §18).
