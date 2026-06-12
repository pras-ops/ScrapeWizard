# 🎨 ScrapeWizard — Frontend Plan (The Application)

> The GUI users actually open: load API key + provider → add a website URL → record the task →
> get a generated script in a suite → run / edit / view results — all inside one platform.
> This is **Milestone M3** of [PLATFORM_PLAN.md](PLATFORM_PLAN.md) and the build steps in
> [BUILD_GUIDE.md](BUILD_GUIDE.md) Stage 3.
>
> **Decisions (locked):** local **web app** (`scrapewizard start` → opens in browser, not
> Electron for v1) · **launch-alongside** record browser · engine = the working Stage 2 code.

---

## 0. Can I start now (Stage 2 is done)? — Yes, but mind one dependency

The Stage 2 engine works as **Python functions / CLI**, not HTTP. A web UI needs an API. So:

```
  Stage 2 engine (done)        →   Backend API (thin, NEW)   →   Frontend (NEW)
  record / generate / sandbox      FastAPI endpoints +            React screens
  / checks  (functions)            SQLite persistence            call the API
```

**Rule that prevents drift:** for every screen, the **API contract (§7) is agreed first**, then
backend + frontend are built against it. You can mock the API in the frontend to move in
parallel, but the contract is the single source of truth.

**You can start today** by: (1) standing up the backend skeleton (§7), (2) scaffolding the
frontend shell (§3–4), (3) building screens as vertical slices (§8 order).

---

## 1. Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Framework | React + Vite | already scaffolded in `studio/frontend/` |
| Language | TypeScript | typed API models = fewer integration bugs |
| Routing | React Router | multi-screen app |
| Server state | TanStack Query (React Query) | caching, polling runs, mutations |
| UI components | shadcn/ui (default) or Mantine | fast, accessible, themeable |
| Styling | Tailwind (comes with shadcn) | tokens + dark mode trivial |
| Forms | React Hook Form + Zod | validation for settings/URL forms |
| Live updates | WebSocket (native) | live run progress |
| Icons | lucide-react | ships with shadcn |

> If TS is a hurdle, plain JS works — but typed API models pay for themselves here.

---

## 2. Design System (build this before screens)

- **Tokens:** one accent color; semantic colors — `passed`=green, `failed`=red,
  `healed`=amber, `running`=blue (pulse), `queued`=gray, `skipped`=muted.
- **Dark mode from day one** (developer audience; trivial with Tailwind tokens).
- **Typography:** 2 heading sizes + body + mono (for selectors/code). 4/8px spacing grid.
- **The four states every list/screen must ship** (non-negotiable — PLATFORM_PLAN §19.2):
  - **Empty** — designed, with one clear CTA (never a blank table)
  - **Loading** — skeletons, not spinners; narrate long ops ("Launching browser…")
  - **Error** — human sentence + next action + "copy details" (no raw tracebacks)
  - **Partial** — a run with 3/10 steps done renders cleanly; refresh recovers state
- **Keyboard:** `r` run, `/` focus search, `Esc` close panel. Visible focus rings.
- **Responsive:** target laptop (1280px) first; mobile = read-only later.
- **Eat our own dog food:** the portal must pass its own axe-core a11y check in CI.

---

## 3. App Shell & Layout

```
┌───────────────────────────────────────────────────────────┐
│ Top bar: logo · current project/env · AI status pill · ⚙   │
├──────────┬────────────────────────────────────────────────┤
│ Sidebar  │  Main content (routed screen)                   │
│  Dashboard                                                  │
│  Tests   │                                                  │
│  Runs    │                                                  │
│  Settings│                                                  │
└──────────┴────────────────────────────────────────────────┘
```

- **AI status pill** (always visible): shows `AI: Off` / `Creation` / `Full` + running cost.
  Reinforces the bounded-cost promise on every screen.
- First launch with no API key → gentle banner: "Running locally, no AI. Add a key in Settings
  to enable AI generation." (App is fully usable with zero key.)

---

## 4. Routes

| Route | Screen |
|---|---|
| `/` | Dashboard |
| `/settings` | Settings (API key, provider, AI mode, thresholds) |
| `/tests` | Tests list (the suite) |
| `/tests/new` | New Test (enter URL → record) |
| `/tests/:id` | Step Manager (test detail: steps, edit, export, run) |
| `/runs/:runId` | Run view (live + result + report) |
| `/runs` | Run history |

---

## 5. Screens — Detailed Spec

Each screen: **Purpose · Layout · Components · States · Data/API · Interactions · Done-when.**

### 5.1 Settings  *(your "load API key, select provider")*
- **Purpose:** configure AI provider + key, AI mode, visual threshold. App works without it.
- **Layout:** a form, sectioned: **AI Provider**, **AI Mode**, **Run defaults**.
- **Components:**
  - Provider select: `OpenAI · Anthropic · OpenRouter · Local (Ollama)` (matches `LLMClient`).
  - API key input (password field; "Test connection" button → calls backend probe).
  - Model input/dropdown (per provider).
  - AI mode radio: **Off** (zero calls) · **Creation** (1–2 calls/test) · **Full** (+ heal recovery).
    Each option shows its cost implication inline.
  - Visual-diff threshold slider; heal auto-accept toggle (placeholder until Stage 4).
  - Artifact retention ("keep last N runs").
- **States:** empty (no key → "AI features disabled, app still works"); saved (toast);
  test-connection loading/success/error.
- **Data/API:** `GET/PUT /settings`; `POST /settings/test-connection`. Key stored via keyring
  on the backend — **never echoed back to the UI** (show "•••• set" once saved).
- **Done-when:** set a key, "Test connection" passes, AI pill updates to chosen mode.

### 5.2 Dashboard  *(home / "is everything green?")*
- **Purpose:** at-a-glance health + entry points.
- **Layout:** stat cards row + recent-runs list + a pass/fail trend sparkline.
- **Components:** cards (Total tests, Pass rate 7d, Runs today, AI spend); RecentRuns table;
  big **"+ New Test"** CTA; empty state → "Record your first test" + "Try the demo".
- **Data/API:** `GET /stats`, `GET /runs?limit=10`.
- **Done-when:** loads real numbers; empty state guides a brand-new user.

### 5.3 New Test  *(your "add the link of the website to test")*
- **Purpose:** start a test from a URL.
- **Layout:** centered card: URL input + name (optional) + **"Start Recording"** button.
- **Components:** URL field (Zod-validated `http(s)://`); env picker (later); helper text
  ("A browser window will open — perform the actions you want to test, then close it").
- **Data/API:** `POST /tests {url, name}` → returns `test_id`; then `POST /tests/:id/record`.
- **Interactions:** clicking Start → backend launches the **alongside** Chromium recorder →
  frontend shows a "Recording in progress… close the browser window when done" state, polling
  `GET /tests/:id/record/status` → on finish, navigate to `/tests/:id` (Step Manager) with
  steps populated. **Instant payoff: user lands on their captured steps.**
- **Done-when:** enter URL → record 3 actions → land on Step Manager showing 3 steps.

### 5.4 Record state  *(your "do the task it wants")*
- **Purpose:** capture the flow while the separate browser is open.
- **Layout:** a waiting panel in the app: live step counter ("4 steps captured"), list of
  captured actions appearing in real time, ⚠ warnings (canvas/shadow-DOM/iframe — your
  recorder already emits these), and a **"Done / I closed the browser"** affordance.
- **Data/API:** WebSocket `/tests/:id/record/live` streaming each captured step, OR poll
  `record/status`. (WS is nicer; poll is simpler for v1.)
- **Done-when:** steps appear live; closing the browser finalizes `flow.json`.

### 5.5 Step Manager (Test detail)  *(your "script in a suite he can run or modify")*
- **Purpose:** view/edit the generated test; run it; export it. **The core screen.**
- **Layout:** header (name, URL, Run ▶, Export, Generate-with-AI) + ordered **step cards**.
- **Each step card shows:**
  - action badge (navigate/click/fill) + generated name
  - **selector ladder** (primary + fallbacks, mono font) — editable
  - value (masked for passwords)
  - assertions (visible/url/…) — add/edit/remove
  - inline screenshot crop thumbnail (from the fingerprint)
- **Editing:** reorder (drag), delete, edit selector/value/assertions → `PUT /tests/:id`.
- **Generate code:** **"Generate with AI"** (if key set) vs the default **local template** —
  both produce the runnable test; show which was used.
- **Export:** **"Export pytest"** → downloads the standalone file (`export_pytest` exists).
- **Data/API:** `GET /tests/:id` (steps), `PUT /tests/:id`, `POST /tests/:id/export`,
  `POST /tests/:id/run` → `run_id`.
- **States:** empty (no steps → "re-record"); editing (dirty + Save); generating (spinner).
- **Done-when:** edit a selector, save, run, see it pass; export downloads a working file.

### 5.6 Run view (Live + Result)  *(your "run test")*
- **Purpose:** watch a run and read its outcome.
- **Layout:** top status banner (running/passed/failed + duration); vertical step timeline
  turning green/red live; right panel = selected step's evidence.
- **Step evidence panel:** screenshot, visual diff (before/after/diff), console errors,
  network 4xx/5xx, a11y violations (impact-coded), heal note (Stage 4), error message.
- **Failure triage:** banner deep-links to the **first failing step** (PLATFORM_PLAN §19.3).
- **Data/API:** `POST /tests/:id/run` then WebSocket `/runs/:runId/live`; final `GET /runs/:runId`.
  (Maps directly to your `RunResult`/`StepResult` shapes — §7.)
- **Done-when:** run a test, watch steps update without refresh, open evidence on a step.

### 5.7 Run history
- **Purpose:** past runs, filterable.
- **Layout:** table (test, status, when, duration, AI cost) + filters (test/status/date).
- **Data/API:** `GET /runs?test_id=&status=&from=&to=`.
- **Done-when:** filter to a test's failed runs; click → Run view.

---

## 6. Reusable Component Inventory

`StatusPill` · `StepCard` · `SelectorLadder` (editable) · `AssertionEditor` ·
`ScreenshotThumb` / `ScreenshotLightbox` · `VisualDiffViewer` (before/after/diff tabs) ·
`A11yViolationList` · `ConsoleNetworkList` · `RunTimeline` · `StatCard` · `EmptyState` ·
`ErrorState` (with "copy details") · `LoadingSkeleton` · `AiStatusPill` · `ProviderForm`.

---

## 7. API Contract (frontend ↔ backend) — agree FIRST

Grounded in the data shapes the engine already produces.

```
Settings   GET  /settings                      -> {provider, model, ai_mode, has_key, visual_threshold, retention}
           PUT  /settings                       <- {provider?, model?, ai_mode?, api_key?, ...}
           POST /settings/test-connection       -> {ok, message}

Tests      GET  /tests                          -> [{id, name, url, step_count, last_run:{status,at}}]
           POST /tests                          <- {url, name?}  -> {id}
           GET  /tests/{id}                      -> {id, name, url, steps:[Step]}
           PUT  /tests/{id}                      <- {name?, steps?}
           DELETE /tests/{id}
           POST /tests/{id}/record               -> {status:"started"}     (launches browser)
           WS   /tests/{id}/record/live          -> stream Step as captured
           GET  /tests/{id}/record/status        -> {recording, step_count}
           POST /tests/{id}/generate             <- {mode:"local"|"ai"} -> {steps}
           POST /tests/{id}/export               -> pytest file (download)
           POST /tests/{id}/run                  -> {run_id}

Runs       GET  /runs?test_id=&status=&...       -> [RunSummary]
           GET  /runs/{run_id}                    -> RunResult   (= sandbox RunResult shape)
           WS   /runs/{run_id}/live               -> stream StepResult as each completes

Meta       GET  /health                          -> {status, schema_version}
           GET  /stats                            -> {tests, pass_rate_7d, runs_today, ai_spend}
```

**Step** (Step Manager) = `{name, action, value, selectors:[{kind,value}], assertions:[{kind,value}], fingerprint?}`
— exactly `TestGenerator.generate()` output.
**RunResult / StepResult** = the sandbox dataclasses (`status, step_results[], duration_ms,
artifacts_dir, ai_calls, ai_cost_usd` / `step_name, status, duration_ms, screenshot_path,
visual_diff_score, console_errors[], network_errors[], a11y_violations[], healed, error_message`).
→ The frontend renders these **as-is**; no reshaping needed.

> Artifacts (screenshots/diffs) served via `GET /artifacts/{run_id}/{file}` (static mount).

---

## 8. Build Order (vertical slices — ship a working thing each step)

1. **Shell + design system + dark mode** (§2–4). Empty routes render.
2. **Settings** (§5.1) — first real screen; unblocks AI later, simplest API.
3. **New Test → Record → Step Manager** (§5.3–5.5) — the spine: URL → record → see steps.
   *(Backend: `POST /tests`, record launch + status, `GET /tests/:id`.)*
4. **Run view** (§5.6) — Run ▶ → live → result. *(Backend: run + `GET /runs/:id` + WS.)*
5. **Export pytest** button (§5.5) — quick win, engine already supports it.
6. **Dashboard + Run history** (§5.2, §5.7) — overview once data exists.
7. **Polish:** all four states on every screen, keyboard shortcuts, self-a11y check in CI.

**First demo-able slice = after step 4:** enter URL → record → see/edit steps → run → watch
green/red → read report. That is the product you described, end to end.

---

## 9. Definition of Done (per screen)
- All four UI states implemented (empty/loading/error/partial).
- Talks to the real API (no mock left behind).
- Keyboard-accessible; passes axe-core.
- Dark + light mode both correct.
- Loading/refresh never loses state.

---

## 10. Out of scope for v1 frontend (defer — PLATFORM_PLAN §16)
Drag-drop flow designer · reusable component library · environments UI · scheduling ·
team/RBAC · embedded in-app browser (we launch alongside) · Electron packaging.
These are Wave 2 — only after the above is used.
