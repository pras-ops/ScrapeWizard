# 🧱 ScrapeWizard — Application Build Steps (Backend Foundation → Frontend)

> The execution sequence for building the GUI app. Feature detail lives in
> [FRONTEND_PLAN.md](FRONTEND_PLAN.md); the *order of operations* lives here.
>
> **Golden rule:** the backend API is built **first** because every screen needs it. Then
> screens are added as **vertical slices** (one screen + the endpoints it uses), each shippable.
>
> **Locked:** local web app (`scrapewizard start`) · launch-alongside recorder · Stage 2 engine.

---

# PART A — Backend API Skeleton + SQLite (the foundation)

The backend is a **thin HTTP layer over the working Stage 2 engine**. It does three jobs:
expose the engine over REST/WS, persist tests & runs in SQLite, serve the built frontend.

**Engine functions it wraps (all exist, verified working):**
- `InteractiveRecorder(output_path, screenshots_dir, headless=False).start(url)` → writes `flow.json`
- `TestGenerator(flow_path).generate()` → `{url, steps:[...]}` · `.export_pytest(path)` → file
- `SandboxRunner(artifacts_dir, baselines_dir, headless).run(test_def)` → `RunResult`
- `LLMClient(provider, api_key, model)` → for Settings test-connection
- keyring via `scrapewizard/utils/security.py` → for storing the API key

### Step A1 — Dependencies & structure
- **Do:** add `sqlmodel` (and confirm `fastapi`, `uvicorn`, `websockets`) to `requirements.txt`
  + `pyproject.toml`. Create the backend module layout under `studio/backend/`:
  ```
  studio/backend/
    main.py            # FastAPI app, CORS, static mount, router registration (exists — extend)
    db.py              # SQLite engine + session, create_all, schema_version
    models.py          # SQLModel tables
    routes_settings.py
    routes_tests.py
    routes_runs.py
    run_executor.py    # background run worker + WS hub
    deps.py            # shared dependencies (DB session, paths)
  ```
- **Done-when:** `uvicorn studio.backend.main:app` boots; `GET /health` returns ok.

### Step A2 — Database setup (`db.py`)
- **Do:**
  1. SQLite at `~/.scrapewizard/studio.db` (create dir if missing).
  2. SQLModel `engine` + a `get_session()` dependency.
  3. `init_db()` → `SQLModel.metadata.create_all()`; store a `schema_version` row.
  4. Artifacts root at `~/.scrapewizard/artifacts/`, baselines at `~/.scrapewizard/baselines/`
     (matches the sandbox default — keep them consistent).
- **Done-when:** first boot creates the `.db` file; `GET /health` reports `schema_version`.

### Step A3 — Models (`models.py`)  *(minimal set for v1 — expand later per PLATFORM_PLAN §12)*
```
Setting     key (PK), value                    # provider, model, ai_mode, thresholds (NOT the key)
Test        id, name, url, created_at, updated_at
Step        id, test_id(FK), order, action, value, selectors(JSON), assertions(JSON), fingerprint(JSON)
Run         id, test_id(FK), status, started_at, finished_at, duration_ms, ai_calls, ai_cost_usd
StepResult  id, run_id(FK), step_name, status, duration_ms, screenshot_path,
            visual_diff_score, console_errors(JSON), network_errors(JSON),
            a11y_violations(JSON), healed, error_message
```
- **Note:** `Step.selectors/assertions/fingerprint` mirror `TestGenerator.generate()` output, and
  `StepResult` mirrors the sandbox dataclass → storage = direct dump, no translation.
- The **API key is NOT a DB column** — it lives in keyring (`Setting` only records `has_key`).
- **Done-when:** tables create cleanly; a manual insert/select round-trips.

### Step A4 — Settings router (`routes_settings.py`)  → unblocks the Settings screen
- **Endpoints:**
  - `GET /settings` → `{provider, model, ai_mode, has_key, visual_threshold, retention}`
    (read from `Setting` rows; `has_key` = does keyring hold one).
  - `PUT /settings` → upsert `Setting` rows; if `api_key` present, store it in keyring
    (`security.py`) and **never store/echo it in the DB or response**.
  - `POST /settings/test-connection` → build `LLMClient(provider, key, model)`, do a tiny
    probe call; return `{ok, message}`.
- **Done-when:** `curl PUT /settings` saves; `GET` shows `has_key:true`; bad key → test fails clearly.

### Step A5 — Tests router (`routes_tests.py`)  → unblocks New Test + Step Manager
- **Endpoints:**
  - `POST /tests {url, name?}` → create `Test`, return `{id}`.
  - `GET /tests` → list with `step_count` + `last_run`.
  - `GET /tests/{id}` → test + ordered `Step`s.
  - `PUT /tests/{id}` → update name / steps (edits from Step Manager).
  - `DELETE /tests/{id}`.
  - `POST /tests/{id}/record` → **launch the alongside recorder as a background task**
    (see A6 note); returns `{status:"started"}`.
  - `GET /tests/{id}/record/status` → `{recording: bool, step_count}`.
  - `POST /tests/{id}/generate {mode:"local"|"ai"}` → run `TestGenerator` (local) or AI path
    (Stage 5); persist resulting `Step`s.
  - `POST /tests/{id}/export` → `TestGenerator.export_pytest(...)` → return file download.
  - `POST /tests/{id}/run` → enqueue a run (A7), return `{run_id}`.
- **Done-when:** create a test, record against it, `GET /tests/{id}` shows captured steps.

### Step A6 — Recording as a background task (the one tricky bit)
- **Why:** `InteractiveRecorder.start()` opens a **headed browser and blocks until the user
  closes it** — you cannot await it inside a request handler.
- **Do:**
  1. `POST /tests/{id}/record` spawns an `asyncio` task running the recorder, writing
     `flow.json` into the test's working dir; set an in-memory `recording[test_id]=True`.
  2. Frontend polls `record/status` (or subscribe via WS `/tests/{id}/record/live`).
  3. When the browser closes → recorder finishes → backend reads `flow.json`, runs
     `TestGenerator.generate()`, and **persists the steps** to the `Step` table; flips status off.
- **Done-when:** click record (via curl trigger), perform actions, close browser → steps land in DB.

### Step A7 — Runs router + executor (`routes_runs.py`, `run_executor.py`)  → unblocks Run view
- **Do:**
  1. `POST /tests/{id}/run` → create `Run(status="queued")`, spawn a background task.
  2. Executor: build `test_def` from the test's `Step`s → `SandboxRunner(...).run(test_def)`
     → write `StepResult` rows → update `Run` to passed/failed + duration; emit progress over WS.
  3. `GET /runs/{run_id}` → `Run` + its `StepResult`s (= the sandbox `RunResult` shape).
  4. `GET /runs?test_id=&status=` → history.
  5. `WS /runs/{run_id}/live` → push each `StepResult` as it completes.
- **Simpler v1 fallback:** if WS is too much at first, make `POST /run` block and return the
  full `RunResult`; add live WS later. (Frontend can poll `GET /runs/{id}` meanwhile.)
- **Done-when:** trigger a run → `GET /runs/{id}` returns per-step results + screenshots paths.

### Step A8 — Artifacts static mount
- **Do:** mount `~/.scrapewizard/artifacts/` at `GET /artifacts/{run_id}/{file}` so the frontend
  can load screenshots and diff images by URL.
- **Done-when:** a screenshot path from a run loads in the browser.

### Step A9 — `scrapewizard start` command
- **Do:** new CLI command that (1) `init_db()`, (2) runs uvicorn on `127.0.0.1`, (3) serves the
  **built** frontend (`studio/frontend/dist`) as static files at `/`, (4) opens the browser.
  Bind localhost only (security, already set). Keep CORS for the Vite dev origin during dev.
- **Done-when:** `scrapewizard start` opens the app shell in the browser.

### Step A10 — Verify the backend before touching the frontend
- **Do:** a smoke script (or REST client) that walks: `PUT /settings` → `POST /tests` →
  (`record` manually) → `GET /tests/{id}` → `POST /run` → `GET /runs/{id}`.
- **Done-when:** the whole loop works over HTTP with **no frontend** — the API is real and trusted.

> ✅ **End of Part A:** the engine is fully drivable over HTTP + persisted in SQLite. Now the
> frontend is "just" a client of a working API — exactly the position you want to build a UI from.

---

# PART B — Frontend, step by step

Build as vertical slices; each slice ends with something you can click. Detail per screen is in
[FRONTEND_PLAN.md](FRONTEND_PLAN.md) §5 — this is the sequence + setup.

### Slice 0 — Scaffold & plumbing
- **Do (in `studio/frontend/`):**
  1. Confirm Vite + React; add TypeScript if not present.
  2. Install: `react-router-dom`, `@tanstack/react-query`, `tailwindcss`, `shadcn/ui` (init),
     `react-hook-form`, `zod`, `lucide-react`.
  3. Set up Tailwind + design tokens + **dark mode** (semantic colors: passed/failed/healed/
     running/queued).
  4. Create `src/lib/api.ts` — a typed fetch client pointing at `http://127.0.0.1:8000`
     (env var for prod vs dev). One place for all API calls.
  5. Create `QueryClientProvider`, `RouterProvider`.
- **Done-when:** `npm run dev` shows a themed blank app; dark mode toggles.

### Slice 1 — App shell + the four state components
- **Do:**
  1. Layout: sidebar (Dashboard / Tests / Runs / Settings) + top bar (logo, **AI status pill**).
  2. Define routes (FRONTEND_PLAN §4) with placeholder pages.
  3. Build the reusable primitives **now** (everything depends on them): `EmptyState`,
     `LoadingSkeleton`, `ErrorState` (with "copy details"), `StatusPill`.
- **Done-when:** navigation works; every placeholder renders an EmptyState.

### Slice 2 — Settings screen  *(simplest real screen; uses A4)*
- **Do:** provider select (OpenAI/Anthropic/OpenRouter/Local), API key field, model field,
  AI mode radio (Off/Creation/Full), threshold slider. "Test connection" button →
  `POST /settings/test-connection`. Save → `PUT /settings`. Show `has_key` as "•••• set".
- **Done-when:** save a key, test connection passes, AI pill updates.

### Slice 3 — The spine: New Test → Record → Step Manager  *(uses A5 + A6)*
- **Do:**
  1. **New Test** (`/tests/new`): URL form (Zod), name optional → `POST /tests` → then
     `POST /tests/{id}/record`.
  2. **Record state:** waiting panel polling `record/status` (or WS), showing live step count +
     ⚠ warnings; on finish → navigate to `/tests/{id}`.
  3. **Step Manager** (`/tests/{id}`): render ordered `StepCard`s (action, **editable selector
     ladder**, value, assertions, screenshot thumb). Edit/reorder/delete → `PUT /tests/{id}`.
     Buttons: **Run ▶** (`POST /run`), **Generate** (local/AI), **Export pytest**.
- **Done-when:** enter URL → record 3 actions → see them as editable steps → edit one → save.

### Slice 4 — Run view (live + result)  *(uses A7 + A8)*
- **Do:** on Run ▶ → navigate to `/runs/{run_id}`; subscribe to WS (or poll `GET /runs/{id}`);
  render `RunTimeline` (steps green/red) + an evidence panel per step: screenshot (from
  `/artifacts/...`), `VisualDiffViewer`, `A11yViolationList`, `ConsoleNetworkList`, error msg.
  Status banner deep-links to the first failing step.
- **Done-when:** run a test, watch steps update, open evidence; failed run highlights the failure.

### Slice 5 — Export button polish
- **Do:** wire **Export pytest** in Step Manager to `POST /tests/{id}/export` → download the
  standalone file. (Engine already produces it.)
- **Done-when:** downloaded file runs as a standalone `pytest` outside the app.

### Slice 6 — Dashboard + Run history  *(uses /stats, /runs)*
- **Do:** Dashboard stat cards + recent runs + empty state ("Record your first test" / "Try the
  demo"). Run history table with filters → click → Run view.
- **Done-when:** dashboard shows real numbers; history filters to a test's failed runs.

### Slice 7 — Polish & a11y
- **Do:** ensure **all four states** on every screen; keyboard shortcuts (`r`, `/`, `Esc`);
  run the portal through axe-core in CI (we ship an a11y checker — it must pass its own).
- **Done-when:** clean empty/loading/error states everywhere; portal passes its own a11y scan.

---

## First demo-able product = end of Slice 4
Enter a URL → record the task → see/edit the generated steps → run → watch it pass/fail live →
read the report. That is the exact application you described, working end to end, no API key
required (AI optional via Settings).

## Suggested commit checkpoints
- After **A10** (backend drivable over HTTP) — a clean foundation commit.
- After each frontend slice (0→7) — each is independently shippable.

## Dependency note
Part B Slice N assumes the Part A endpoints it lists are done. If building solo, do
**A1–A5 → Slice 0–2 → A6/A7 → Slice 3–4 → rest** so backend and frontend interleave naturally.
