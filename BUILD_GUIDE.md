# 🧭 ScrapeWizard — Build Guide (How To Do Each Stage)

> **Companion to [PLATFORM_PLAN.md](PLATFORM_PLAN.md).** The plan says *what* and *why*; this
> guide says *how* — concrete actions, commands, code skeletons, acceptance checks, and
> pitfalls for each stage of §29. Work top to bottom. Check a box only when its acceptance
> check passes.
>
> **How to use:** each step has **Goal → Do → Verify → Pitfalls**. Don't skip Verify — the
> whole project's failure mode (a green test suite hiding a broken product) is what these checks exist to prevent.

---

## Conventions

- **Branch per stage:** `git checkout -b stageN-short-name`; small commits; PR into `main`.
- **Commit style:** Conventional Commits — `fix:`, `feat:`, `chore:`, `docs:`, `test:`.
- **Run tests constantly:** `pytest tests/ -q --ignore=tests/golden_sites`.
- **Definition of done for any step:** code + test + its acceptance check green in CI.

---

## ✅ STAGE 0 — Unbreak & Guard (DONE 2026-06-11)

All items complete and verified. Recorded here so the guide is a full history.

| Step | What was done | Verify (re-runnable) |
|---|---|---|
| Critical bugs | `LLMClient` import, `yaspin` dep, `WebSocketDisconnect` import | `pytest tests/core/test_orchestrator_construction.py -v` |
| Cleanup | dead code, duplicate `logs/` copy, `pagination_config` helper, BS4 `string=`, bare excepts, dead studio funcs | `pytest tests/ -q --ignore=tests/golden_sites` → 25 passed |
| Security | backend binds `127.0.0.1`, CORS locked to portal origins | read `studio/backend/main.py` |
| CI guards | construction test + fresh-install matrix | `.github/workflows/ci.yml` runs on PR |

➡️ **You are here.** Next real work is Stage 1.

---

## STAGE 1 — Foundation (Milestone M1) — *IN PROGRESS*

Goal of the stage: a recorded flow produces rich **element fingerprints**, and a **selector
engine** turns DOM into ranked CSS+XPath ladders. This is the keystone for everything.

> **Status (2026-06-11):** foundation landed in commit `572ded9` —
> `scrapewizard/engine/selector_engine.py`, `scrapewizard/engine/fingerprint.py`,
> `scrapewizard/demo_app/` (+ mutation tests). Note actual paths are **`scrapewizard/engine/`**
> and **`scrapewizard/demo_app/`** (not top-level). Remaining: Step 1.1 (name), the recorder
> upgrade (Step 1.5), and wiring fingerprint capture into live recording.

### Step 1.1 — Decide the product name *(your call; unblocks branding/PyPI)*
- **Goal:** stop calling a test platform "ScrapeWizard."
- **Do:**
  1. Brainstorm 5–10 names. Constraints: testing-flavored, not "scrape," short.
  2. Check availability for the top 2: PyPI (`pip index versions <name>` or pypi.org), GitHub
     org/repo, domain, a basic trademark search.
  3. Record the decision in PLATFORM_PLAN.md §18 + open decision #5.
- **Verify:** name chosen, PyPI name free.
- **Pitfall:** don't rename packages in code yet — just decide. Mechanical rename happens at M3
  packaging, after the engine exists.

### Step 1.2 — Build the bundled demo app ✅ *(landed `572ded9` at `scrapewizard/demo_app/`)*
- **Goal:** one tiny local site that serves as (a) offline demo, (b) healing fixtures, (c) E2E target.
- **Do:**
  1. Create `demo_app/` — a static site (plain HTML/CSS/JS, no framework needed): a product
     grid (cards with title, price, image, "add to cart" button) + a 2-page pagination + a
     simple login form. Keep it deterministic (hard-coded data).
  2. Add a tiny launcher: `python -m http.server` wrapper or a FastAPI static mount, callable
     as `scrapewizard demo-app` later. For now a `demo_app/serve.py` is fine.
  3. Create `demo_app/mutations/` — copies of the page with one change each (see §9.4 of the
     plan): class renamed, id removed, element moved, text reworded, sibling inserted,
     attribute changed, element removed. These power the healing suite in Stage 4.
- **Verify:** `python demo_app/serve.py` serves the page at a local URL; you can click through it.
- **Pitfall:** make the markup *realistic* (some stable `data-test` attrs, some only-class
  elements, one CSS-in-JS-looking hashed class) so the selector engine is actually exercised.

### Step 1.3 — Selector Engine (`scrapewizard/engine/selector_engine.py`) ✅ *(landed `572ded9`)*
- **Goal:** for any element, produce a ranked CSS+XPath strategy ladder, container-relative.
- **Do:**
  1. `scrapewizard/engine/__init__.py` (done).
  2. Implement `build_strategies(element, container) -> list[Strategy]` following PLAN §8:
     stable attrs → semantic classes → anchored XPath → positional XPath.
  3. Implement `is_stable_class(cls) -> bool`: reject `css-1a2b3c`, `sc-…`, `jsx-…`,
     Tailwind atomics (`mt-4`,`flex`,`text-sm`), digit-heavy/random tokens; accept human names.
     (Start from `dom_analyzer._is_safe_class` and extend it.)
  4. Implement XPath builders: relative `.//tag[contains(@class,'x')]` and positional fallback.
- **Verify:** write `tests/engine/test_selector_engine.py` using saved HTML from the demo app.
  Assert: ≥2 strategies + ≥1 XPath per element; `css-1a2b3c` rejected, `price` accepted.
- **Pitfall:** always emit a positional XPath as the last resort so the ladder is never empty.

### Step 1.4 — Element Fingerprint (`scrapewizard/engine/fingerprint.py`) ◑ *(module landed `572ded9`; verify schema coverage + live capture)*
- **Goal:** capture every signal self-healing will later need (PLAN §7).
- **Do:**
  1. Define a `Fingerprint` dataclass/Pydantic model matching the §7 schema: selectors,
     tag, attributes, text, context (parent/siblings/ancestors/index), geometry
     (incl. viewport-normalized `x_pct/y_pct`), visual (crop path + neighborhood hash),
     navigation, history.
  2. Implement `capture(page, element_handle) -> Fingerprint`: uses Playwright
     `evaluate` to walk the DOM and read `getBoundingClientRect`; calls the selector engine
     for the ladder; takes a small screenshot crop via `element.screenshot()`.
  3. Implement `to_dict()/from_dict()` for DB storage; keep ≤5 KB + the crop image.
- **Verify:** `tests/engine/test_fingerprint.py` — capture an element from the demo app,
  assert all fields populated and JSON round-trips.
- **Pitfall:** normalize text (strip/collapse whitespace) and coordinates (divide by viewport)
  *at capture time* — healing depends on them being normalized.

### Step 1.5 — Recorder upgrade
- **Goal:** every recorded action carries a full fingerprint.
- **Do:**
  1. Extend the existing `browser.start_interactive_recording()` (`scrapewizard/recon/browser.py`)
     so each captured event calls `fingerprint.capture()` for its target element.
  2. Reuse `studio/bridge/engine.js` overlay to highlight what was captured.
  3. Auto-insert assertions: on URL change → URL assertion; on element appearance → visibility wait.
  4. Detect unsupported constructs (iframe/shadow-DOM/canvas) and emit a clear warning into the
     flow (don't fail silently — PLAN risk R2).
  5. Output `flow.json`: ordered steps, each `{action, value?, fingerprint}`.
- **Verify:** record a 5-step flow on the demo app; open `flow.json`; confirm 5 steps each with
  selectors, context, geometry, crop path, navigation.
- **Pitfall:** mask `input[type=password]` values at capture (store placeholder) — never write
  real passwords into `flow.json` (PLAN §24).

**Stage 1 exit:** recorded demo flow → `flow.json` with full fingerprints; engine unit tests green.

---

## STAGE 2 — Engine Runs (Milestone M2)

Goal: turn a `flow.json` into a runnable test and execute it in a sandbox with checks.

### Step 2.1 — Test generation, template mode (`engine/test_generator.py`)
- **Goal:** `flow.json` → internal step list + an exported standalone pytest file. No AI yet.
- **Do:**
  1. `generate(flow) -> Test`: deterministic step naming (`click_checkout`, `fill_email`),
     standard assertions from the recorded ones.
  2. `export_pytest(test) -> str`: render a runnable `pytest` + Playwright file from a Jinja
     template; embed the healing resolver call per step (resolver stub for now, real in Stage 4).
- **Verify:** record login flow → generate → the exported `.py` runs standalone and passes.
- **Pitfall:** the exported file must be self-contained (no import from the platform internals
  the user won't have) — this is the anti-lock-in promise.

### Step 2.2 — Sandbox runner (`engine/sandbox.py`)
- **Goal:** execute a test in an isolated browser context, collect results + artifacts.
- **Do:**
  1. `run(test, env) -> RunResult`: fresh Playwright context per run; replay each step via the
     resolver; per-step timeout + global timeout; capture screenshot per step.
  2. Wire the deterministic **checks** (new `engine/checks/`): `console_network.py` (console
     errors + 4xx/5xx via existing scanner interception), `visual.py` (screenshot vs baseline,
     pixelmatch; first run = baseline), `a11y.py` (inject axe-core, collect violations).
  3. Return per-step status + artifacts; non-zero overall on any failure.
- **Verify:** golden E2E in CI — record→generate→run on the demo app, assert non-empty pass.
- **Pitfall:** baseline screenshots must be stored per-environment/viewport or every run diffs.

**Stage 2 exit:** record → generated test → sandbox run passes with a full result + artifacts.

---

## STAGE 3 — The Product Appears (Milestone M3) — *first sellable/demo-able*

Goal: the admin portal (Wave 1) over a real API + DB. This is what users evaluate.

### Step 3.1 — Data model (`studio/backend/models.py`)
- **Do:** implement the §12 tables in SQLModel; SQLite at `~/.scrapewizard/studio.db`;
  auto-create on boot; add a `schema_version` row + a no-op migration runner.
- **Verify:** boot backend → DB file created → `GET /health` reports schema version.

### Step 3.2 — API routers (`studio/backend/routes_*.py`) + run executor
- **Do:** implement §13 endpoints split per resource; a background `run_executor.py` that
  consumes a queue, calls `engine.sandbox.run`, writes `StepResult`/`HealEvent`, emits WS events.
- **Verify:** `POST /tests/{id}/run` → a `TestRun` moves queued→running→passed/failed with
  per-step results; `WS /runs/{id}/live` streams progress. Write API contract tests in `tests/studio/`.
- **Pitfall:** keep the executor non-blocking — long runs must not freeze the API event loop.

### Step 3.3 — Security hardening (finish what Stage 0 started)
- **Do:** add a per-session token the portal sends with every request (PLAN §24); mask
  passwords end-to-end; add a retention setting for artifacts.
- **Verify:** requests without the token are rejected; recorded passwords never hit disk.

### Step 3.4 — Portal Wave 1 (`studio/frontend/src/`)
- **Goal:** the 6 screens of PLAN §11, each with all four UI states (PLAN §19.2).
- **Do:**
  1. Set up React Router + React Query + shadcn/ui (or Mantine — decide per §17). Design tokens
     + dark mode first (PLAN §19.1).
  2. Build, in order: **Dashboard → Tests list → Step Manager → Live Run → Run History/Report
     → Settings.** Each ships empty/loading/error/partial states — no blank tables.
  3. Wire the §19.3 flows: record (lands in Step Manager), run-and-watch (auto-opens live view),
     failure triage (leads with first failing step).
- **Verify:** in a browser — record a test, see its steps, run it, watch live green/red, open the
  report. Run the portal through axe-core (PLAN §19.4) — it must pass its own a11y check.
- **Pitfall:** build the empty/error states *with* each screen, not "later" — later never comes.

### Step 3.5 — Onboarding + packaging
- **Do:** `scrapewizard start` (runs API + serves built portal + opens browser); first-run
  bootstrap (detect missing Playwright browsers → offer install; port conflict → next port);
  welcome screen with "Try the demo" + "Record your first test" (PLAN §20). Build the Vite
  bundle into the wheel so users need no Node (PLAN §21).
- **Verify:** on a clean machine (use the CI fresh-install matrix), `pipx install` → `start` →
  demo runs green, on Windows/macOS/Linux.

### Step 3.6 — Docs + beta
- **Do:** README rewrite (tagline, the §22 "money shot" GIF, 3-line quickstart, comparison
  table), quickstart, troubleshooting top-10. Then **beta release** (`pip install --pre`) to
  5–15 recruited testers (PLAN §27).
- **Verify:** a stranger reaches first green report in < 5 min (TTFD metric, PLAN §4).

**Stage 3 exit:** manage/run/monitor/report in the browser; beta out. **Ship the README+GIF here.**

---

## STAGE 4 — The Moat (Milestone M4)

Goal: real self-healing. This is the differentiator and the part that takes the most tuning.

### Step 4.1 — Healing ladder (`engine/healing.py`)
- **Do:** implement tiers 0–5 from PLAN §9, each emitting `(candidate, confidence)`:
  selector ladder → attribute/text scoring → parent/sibling structure → geometry/visual →
  history/navigation. Accept ≥ threshold; **refuse to heal on ambiguous multi-match** (risk R1).
  Persist a heal only after the step **re-runs green**. Append every resolution to fingerprint history.
- **Verify:** the mutation suite (next step).
- **Pitfall:** wrong-element heals are worse than failures — bias toward refusing over guessing.

### Step 4.2 — Mutation fixture suite (`tests/healing_fixtures/`)
- **Do:** use the demo-app mutations from Step 1.2; for each, assert the expected tier resolves
  it, confidence ≥ threshold, and **zero wrong-element matches**. Gate CI on it (PLAN §9.4).
- **Verify:** ≥80% of single-mutation cases heal at tiers 0–5 with **0 AI calls**; 0 wrong matches.
- **Tune here:** thresholds get adjusted against this suite until the gates pass. Budget real time.

### Step 4.3 — Heal review UX
- **Do:** amber "healed" badge per step; side-by-side old/new locator + screenshot; Approve
  (persist + rerank ladder) / Reject (revert + flag). Settings: auto-accept threshold vs always-ask.
- **Verify:** trigger a heal in the demo → badge appears → approve → fingerprint history updated.

**Stage 4 exit:** class-rename and container-move breakages self-heal, 0 AI calls, 0 wrong matches.

---

## STAGE 5 — AI Layer (Milestone M5)

Goal: bounded, optional AI at exactly two moments (PLAN §5).

### Step 5.1 — Creation-time generation
- **Do:** add AI mode to `test_generator`: one structured call (compact fingerprints, **never
  raw HTML**) → human names, extra assertions, component grouping. Template mode stays the default.

### Step 5.2 — Tier-6 recovery
- **Do:** in `healing.py`, when tiers 0–5 fail and `ai_mode=full`, one call → propose locator →
  **verify by re-running the step** before accepting. Log provider/model/tokens/cost to the run.

### Step 5.3 — Cost surfacing + settings
- **Do:** show AI calls + cost per test and per run; Settings toggle `off`/`creation`/`full`.
- **Verify:** a green run records `ai_calls=0, ai_cost=$0.00`; `ai_mode=off` makes zero calls,
  provably, in run metadata.

**Stage 5 exit:** bounded-AI guarantee is demonstrable in the portal.

---

## STAGE 6 — Launch

Goal: public release.

- **Do:** complete the **§30 pre-launch checklist** (every box). Record the 2–3 min demo video
  (the money shot). Final README GIF. Landing = polished README + GitHub Pages.
- **Launch posts:** Show HN, r/QualityAssurance + r/softwaretesting, Ministry of Testing,
  testing newsletters, X/LinkedIn — lead with the money shot, not features.
- **Then:** 48-hour fast response window on issues/comments.
- **Verify:** §30 checklist fully green before any post goes out.

---

## STAGE 7 — Post-Launch

- Triage feedback; tune healing on real-world misses (the healing-miss issue template is gold).
- Start **Wave 2** (M6: drag-drop designer, components, environments, scheduling, RBAC) **only
  if users ask** for specific features (PLAN §16 scope discipline).
- Revisit monetization (PLAN §28) once there's organic usage.

---

## Quick Reference — the loop for every single step

1. Branch. 2. Write the smallest code that could work. 3. Write its test + acceptance check.
4. `pytest` green locally. 5. Push → CI green (incl. fresh-install). 6. PR → merge.
7. Update the relevant ✅ in PLATFORM_PLAN.md. Repeat.
