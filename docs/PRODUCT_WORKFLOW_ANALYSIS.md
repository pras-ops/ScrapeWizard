# 🧭 Product & Workflow Analysis — "Test Everything in One Place"

> **Update:** the §6 decisions have been made. The scraper is the **base engine**, the target is
> **small firms without QA staff**, the primary user is the **user tester**, and reports are
> **shareable**. The resulting design is in [PRODUCT_DIRECTION.md](PRODUCT_DIRECTION.md), which
> supersedes §3 and §5 below where they differ.

> **Question analysed:** the goal is one place where a user loads their app and tests *everything*
> (UI, UX, network and more), with scraping as only the starting point. The user workflow differs
> from normal UI testing and code testing. How should the project change, and what's wrong today?
>
> Inputs: the current codebase (commit `6003e10`, verified by grep and execution), plus
> [COMPETITIVE_RESEARCH.md](COMPETITIVE_RESEARCH.md) and new research on all-in-one platforms,
> capture tools, network-from-traffic testing and performance-in-journey tools (sources at the end).

---

## 1. The core insight: your workflow really is different

Every mainstream testing workflow starts from **specification**: someone decides in advance what
to check, then writes or records a test for that one thing. Your workflow starts from **behaviour**:
a person does the task once, and the tool works out everything worth checking from that one
session.

| Workflow | Who | How a test is born | What one session produces | Where results live |
|---|---|---|---|---|
| **Code-first** (Playwright, Cypress) | SDET / developer | Writes assertions in code upfront | One functional test | CI logs, HTML report |
| **Codeless record/playback** (mabl, Testim, Katalon, Codegen) | QA / manual tester | Records clicks, adds assertions | One functional test (plus healing) | Vendor cloud |
| **Specialist tools** (Postman, Lighthouse, axe, Percy) | Separate specialists | A separate session per tool | One dimension each | Five tools, five reports |
| **Capture tools** (Jam.dev) | Anyone | Clicks "capture" when a bug happens | Video + console + network + steps + device | A shareable bug report, **no replay/regression** |
| **Your vision** | Anyone who can use the app | **Does the task once** | **Functional + network/API + a11y + visual + performance + console, from one recording** | **One local place, one findings list** |

**The short version: record once, check everything, see one list of issues.** That's the product.
It's a real gap. Each close analogue covers only a slice:

- **Jam.dev** captures everything, but only for one-off bug reports. You can't replay it as a regression test.
- **Chrome DevTools Recorder** records, replays and measures performance, but has no checks, no history and no dashboard.
- **Lighthouse user flows** measure performance and a11y inside a journey, but you have to script them in Puppeteer.
- **Keploy / HAR tools** turn browser traffic into API tests, but test nothing in the UI.
- **Playwright Codegen / Healer** cover UI only, and are code-first.
- **Katalon / mabl / Testsigma** are "all-in-one", but code- or cloud-heavy, expensive, and criticised for lock-in and slowness.

Nobody does **one recording → every quality dimension → one deduplicated issue list, locally.**

> **The current code does not implement this workflow.** It implements a
> *record/playback functional tester* with a few side-checks attached. The rest of this document
> explains the gap.

---

## 2. Issues — deep analysis

### A. Identity: two products share one body

| # | Issue | Evidence |
|---|---|---|
| A1 | **The scraper and the tester are separate products that happen to share a repo.** The Studio (the testing product) never calls the scraper pipeline. | `grep Orchestrator|DOMAnalyzer|CodeGenerator` in `studio/` returns nothing |
| A2 | **About 4,700 lines of scraper-only code** (`core/` orchestrator state machine, `llm/` understanding, codegen and repair agents, `recon/`, `interactive/`) serve a product the vision calls "just the starting part." | Line counts by package |
| A3 | **The README headline still leads with scraping:** "Self-Healing Web Scraper Builder & UI/UX Test Automation Studio", "Two Products, One Unified Engine." Visitors can't tell what the product *is*. | `README.md` lines 1–20 |
| A4 | **The CLI mixes both worlds:** `build`/`resume`/`list` (scraper) next to `start`/`record`/`test` (tester), under a name that says "Scrape." | `cli/main.py` |
| A5 | **"UX testing" means something else in the market.** UX testing means usability research with real people (task completion, satisfaction; Maze, UserTesting). What this tool does is **UI, functional and technical-quality testing of user journeys**. Using the word "UX" attracts the wrong buyers and invites a comparison you'll lose. | Industry definitions (Contentsquare, Testsigma, Digivante) |

**What it means:** until the identity is settled, every design decision gets pulled two ways, and
marketing can't make one claim.

### B. The recording, your most valuable asset, is thin

In your workflow **the recording is the source of truth.** Everything should be derived from it.
Right now it captures almost nothing beyond the DOM:

| # | Issue | Evidence |
|---|---|---|
| B1 | The recorder captures only **`click` and `change` DOM events**. No `input`, select, check, keypress, upload or dialog events. | `recorder.py:132-142` |
| B2 | **No network capture during recording.** No HAR, no request/response bodies, no timings. So **network/API tests can't be derived from the recording**, and the whole "network testing" pillar has nothing to work from. | `grep har|on("request"|on("response"|tracing` in `recorder.py`: none |
| B3 | **No console capture during recording.** Baseline console noise is unknown, so every run can't tell "new error" from "always there." | Same grep |
| B4 | **No Playwright trace during recording or replay.** No DOM snapshots over time and no timeline evidence. | Same grep |
| B5 | Login secrets are replaced with `***MASKED***` and **can't be replayed**, which blocks every authenticated app. | `recorder.py` masking |

### C. The network pillar is a side-effect, not a test type

| # | Issue | Evidence |
|---|---|---|
| C1 | The only network feature is a listener that logs responses **≥ 400**. | `checks/console_network.py:20-22` |
| C2 | You can't assert a **specific API call**: "POST /api/checkout returns 200 in under 800 ms and has an `orderId`." | No API assertion model |
| C3 | No request/response schema or contract checks, and no latency budgets. | — |
| C4 | No mocking or replay of the network (Playwright `routeFromHAR`), which you'd need for stable UI tests independent of a flaky backend. | — |

**What it means:** "network testing" is currently a warning count per step, not a capability a
user can design, review or rely on.

### D. Results are raw logs, not findings

| # | Issue | Evidence |
|---|---|---|
| D1 | **A11y runs full-page axe on every step**, so the same violation is reported N times per run. The earlier demo showed the same 2 violations under each step. | `sandbox.py:207` inside the step loop; `test` CLI output |
| D2 | `StepResult` stores **per-step lists** of console, network and a11y. There's no deduplication, severity, first-seen or occurrence count. | `models.py` `StepResult` |
| D3 | **No `Finding`/`Issue` entity.** Nothing can be marked new / known / accepted / fixed across runs, so every run re-reports everything. | `models.py`: no such class |
| D4 | **Mixed pass/fail semantics.** Functional failures fail the run; a11y and visual are silently informational. The user can't set per-dimension policy (block / warn / info). | `sandbox.py` status logic |

**What it means:** "one place" only has value if the one place is **a clean, deduplicated list of
issues across every dimension.** Today it's a pile of per-step logs, which is the problem Jam,
Sentry and Currents exist to solve.

### E. Missing dimensions the vision promises

| Dimension | Status | Best-in-class engine to reuse (don't rebuild) |
|---|---|---|
| Functional flow | ✅ replay + assertions (visible, url) | Playwright |
| Accessibility | ◑ axe per step (duplicated) | axe-core, ideally once per unique page state |
| Visual | ◑ raw PIL pixel diff | pixelmatch-style diff + masking, or Playwright `toHaveScreenshot` |
| Console health | ◑ errors only, no baseline | Playwright console events + a recorded baseline |
| **Network / API** | ❌ 4xx/5xx listener only | HAR capture → derived API assertions (Keploy/HAR pattern) |
| **Performance** | ❌ none | **Lighthouse user flows** (navigation / timespan / snapshot) or Web Vitals via `PerformanceObserver` |
| **Data correctness** (the scraping heritage) | ❌ not in the tester | Your `DOMAnalyzer` repurposed: "extract this list, assert ≥ N items / price format" |
| Security basics (later) | ❌ | Mixed content, cookie flags, security headers from HAR |

Lighthouse's three modes line up exactly with a recorded journey: **navigation** for `goto`
steps, **timespan** for interaction sequences, and **snapshot** after a step. That's a natural
performance pack.

### F. Data model: no home for "everything"

The current schema is `Test → Step → Run → StepResult` (plus `Setting`). It has no place for:

- **Project / App under test**: the thing the user "loads."
- **Environment**: dev, staging and prod base URLs, credentials and variables. The only `base_url`
  in the backend belongs to the *LLM runtime*, not the app (`routes_settings.py:23`).
- **Journey / Recording as an asset**: the raw capture (actions + HAR + console + trace), kept
  separate from any single test derived from it.
- **Check packs and policies**: which dimensions run, and what counts as failure.
- **Findings**: the deduplicated issues with status (§D).
- **Suite / schedule**: groups of journeys run together.

### G. The UI is built for the wrong persona

- The **Step Manager** puts CSS/XPath selector ladders front and centre. That's an engineer's editor.
  The person your workflow targets ("anyone who can use the app") shouldn't have to read XPath.
- In a do-the-task workflow **users don't know what to assert upfront.** The natural UX is
  **review, not write**: after recording, the tool proposes checks ("we saw `POST /api/login`
  return 200, keep checking it?", "3 a11y issues found, set as baseline?", "this timestamp changes
  every run, mask it?") and the user accepts or rejects them. The current UI has no proposal/review
  queue at all.
- **No findings inbox** (see §D), no heal-review queue, no per-dimension summary on a run.

### H. Competitive exposure (from the research)

- Playwright's free Healer and Codegen, and qa-core-heal's safety bar, make **"self-healing" a weak
  headline.** It's table stakes now, not the story.
- The **all-in-one criticism is real**: Katalon is called slow and bloated; Testsigma is called
  locked-in. Breadth without depth fails. **Mitigation:** one shared capture layer, with pluggable
  check packs that each delegate to a best-in-class engine (axe, Lighthouse, Playwright trace,
  pixelmatch) instead of homegrown approximations.
- **Your defensible story:** *record once → full quality report → one issue list → local, no
  subscription, no lock-in (exports to Playwright).*

---

## 3. Proposed product model — "one execution, many lenses"

```
PROJECT (the app under test)
 ├─ Environments: dev / staging / prod → base URL, auth (storageState), variables, secrets
 └─ JOURNEYS (recorded once by a human doing the task)
      Capture = actions + fingerprints + HAR (network) + console + trace + screenshots + timings
      │
      ├─ CHECK PACKS derived from the capture (each has a policy: block / warn / info)
      │    • Functional   — steps + assertions (proposed, then reviewed)
      │    • Network/API  — key calls: status, latency budget, schema, "contains"
      │    • Accessibility— axe once per unique page state, baseline known issues
      │    • Visual       — per-state baselines with masks
      │    • Performance  — Web Vitals / Lighthouse flow per navigation and interaction
      │    • Console      — new errors vs recorded baseline
      │    • Data         — extraction assertions (scraping engine reused here)
      │
      └─ RUN = replay the journey ONCE; every enabled pack evaluates the SAME execution
             (one trace, one HAR, one set of screenshots → consistent and cheap)
                    │
                    ▼
            FINDINGS (deduplicated across steps and runs)
              severity · dimension · evidence (trace/screenshot/request) · first seen
              status: new → known → accepted / fixed · regression flag
                    │
                    ▼
            Findings inbox · run report · CI exit code / JUnit · Playwright export
```

**Principles:**
1. **Capture maximally, check selectively.** Record everything once; packs decide what matters.
2. **Replay once, evaluate many.** Never run the browser six times for six dimensions.
3. **Findings, not logs.** Deduplicate, track status across runs, and surface regressions.
4. **Review, don't write.** The tool proposes checks and the human accepts them.
5. **Delegate to best-in-class engines.** Your value is orchestration, evidence and workflow, not re-implementing axe or Lighthouse.
6. **Deterministic by default, AI optional.** AI can name things, propose assertions and heal as a last resort, always logged. (Your existing philosophy, kept.)

**Where scraping fits:** as the **Data pack** ("extract the product list, assert 20 items with
valid prices") and as the engine that *proposes* data assertions from a page. The standalone CLI
scraper (`build`) is either kept as a separate legacy tool or split into its own package (see §6).

---

## 4. Redesigned user workflow (in the app)

| Step | New workflow | Today |
|---|---|---|
| 1 | **Create project**: app URL, environments, log in once (captured as `storageState`) | Enter a URL per test; no auth replay |
| 2 | **Record journey**: do the task; capture actions, network, console, trace, screenshots | Clicks and field changes only |
| 3 | **Review proposals**: API calls seen, text/visibility assertions, a11y baseline, suggested visual masks, perf baseline. Accept or reject | None; land in a selector editor |
| 4 | **Journey saved** with its enabled check packs and policies | Test = steps |
| 5 | **Run** manually, on a schedule, or in CI: one replay, all packs evaluated | One replay, side-checks per step |
| 6 | **Findings inbox**: new/regression issues across all dimensions, deduplicated, with evidence | Per-step lists, repeated every run |
| 7 | **Triage**: accept known issues, approve or reject heals, export to Playwright/JUnit | Heal approval not implemented |

The engineer view (selector ladder, raw steps) stays available as an **advanced** panel, not the default.

---

## 5. Re-sequenced roadmap

| Phase | Goal | Key work | Replaces / updates |
|---|---|---|---|
| **0. Identity** (days) | One product, one story | Decide the scraper's fate (§6); rename the positioning away from "scraper builder" and "UX testing"; rewrite the README headline | README, PLATFORM_PLAN §1/§18 |
| **1. Capture layer** | The recording becomes the source of truth | Recorder: more event types, **HAR + console + trace capture**, role-first locators, auth via `storageState` + env secrets | BUILD_GUIDE Step 1.5, COMPETITIVE_RESEARCH P0.1/P1.5-9 |
| **2. Domain model** | A home for "everything" | `Project`, `Environment`, `Journey` (+ capture artifacts), `CheckPack`/policy, **`Finding`** with dedup and status | PLATFORM_PLAN §12 |
| **3. Findings engine** | Logs → issues | Dedup across steps and runs; a11y once per page state; per-pack policies; failure classification (locator / assertion / timeout / network / app); regression detection | Fixes §D |
| **4. New check packs** | Deliver the promised dimensions | **Network/API pack** (from HAR), **Performance pack** (Web Vitals / Lighthouse flow), visual masking, console baseline, Data pack | Fixes §C, §E |
| **5. Review-first UX** | Build for the actual persona | Proposal review queue after recording, findings inbox, heal-review queue, per-dimension run summary, engineer panel as advanced | FRONTEND_PLAN, MARKET_READY_PLAN P3 |
| **6. Outputs & CI** | Fit into real pipelines | JUnit XML, exit codes by policy, Playwright TS/pytest export, trace links | MARKET_READY_PLAN P5 |

The frontend refactor in MARKET_READY_PLAN (React Query, primitives, TS strict) still applies. Do
it **alongside Phase 5**, not before Phases 1–3. The UI should be rebuilt around findings and
proposals, not polished around the current per-step model.

**Defer or cut:** drag-drop flow designer, RBAC/teams, scheduling UI (a CLI cron is enough at
first), embedded browser, Electron packaging.

---

## 6. Decisions you need to make

1. **What happens to the scraper?**
   - **(a) Absorb it (recommended):** it becomes the Data pack plus the "propose data assertions"
     helper. Retire `build`'s separate state machine over time.
   - **(b) Split it:** move the scraper to its own package or repo; this one becomes testing-only.
   - **(c) Keep both as is:** not recommended, since it keeps the identity problem (§A).
2. **Who is the primary user?** Pick one for v1:
   - **Manual testers / product people** ("anyone who can use the app"): favours review-first UX,
     findings inbox, no code visible. **Best fit for your "different workflow".**
   - **SDETs / developers:** favours code export, CLI and CI first. Crowded, and Playwright's
     free tools cover it.
3. **Naming:** drop "UX testing" (it means usability research) and "scraper." Something that says
   *record once, check everything* (journey quality, web quality, experience checks) fits better.
   This ties to the existing product-name decision (PLATFORM_PLAN §18).
4. **Local-only or shareable?** Findings are more valuable when shared (a link to a finding with
   its evidence, like Jam). Decide whether v1 stays single-user local or exports shareable reports.

---

## 7. Summary

- **The idea is sound and the gap is real:** nobody offers *record once → every quality
  dimension → one deduplicated issue list, locally.*
- **The current build doesn't implement that idea yet.** It's a record/playback functional tester
  with side-checks, sharing a repo with an unrelated scraper.
- **The biggest structural issues:**
  - (A) split identity
  - (B) a recording that captures no network, console or trace
  - (D) raw per-step logs instead of findings
  - (F) no project, environment or findings data model
  - (G) an engineer-centric UI for a "just do the task" persona
- **Fix order:** identity → capture → model → findings → new check packs → review-first UX → CI.

---

## Sources

- Jam.dev (one-click capture of console, network, steps): https://jam.dev · https://dev.to/namnguyenthanhwork/jamdev-an-effective-tool-for-bug-reproduction-1979
- Chrome DevTools Recorder (record, replay, measure performance, export): https://developer.chrome.com/docs/devtools/recorder/overview
- Lighthouse user flows (navigation / timespan / snapshot): https://web.dev/articles/lighthouse-user-flows · https://github.com/GoogleChrome/lighthouse/blob/main/docs/user-flows.md
- HAR-based API testing: https://dev.tools/blog/har-file-api-testing/ · https://github.com/slve/har.test
- Keploy API test recorder: https://keploy.io/docs/running-keploy/api-testing-chrome-extension/
- Playwright HAR replay: https://qaskills.sh/blog/playwright-network-har-replay-testing
- Generating API tests from HAR with AI (Bondar Academy): https://bondaracademy.com/blog/generate-api-tests-with-ai-playwright
- Katalon vs Testsigma (all-in-one tradeoffs): https://www.testsprite.com/use-cases/en/compare/katalon-vs-testsigma
- Katalon alternatives (criticisms): https://bugbug.io/blog/test-automation-tools/katalon-alternatives/
- UX vs UI testing definitions: https://contentsquare.com/guides/ui-design/testing/ · https://testsigma.com/blog/ui-ux-testing/ · https://www.digivante.com/?p=28391
- Manual testers moving to automation: https://smartbear.com/blog/no-code-no-problem-ai-powered-automation-for-manual-testers/ · https://www.shiplight.ai/blog/low-code-platforms-manual-testers
- Prior research (Playwright agents, qa-core-heal, MoT, HN, Stagehand, Magnitude): see [COMPETITIVE_RESEARCH.md](COMPETITIVE_RESEARCH.md)
