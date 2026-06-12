# 🏁 ScrapeWizard Studio — Market-Standard & Deployment Plan

> The final-mile plan: take the working app (engine ✅, backend API ✅, all 7 screens ✅)
> from "functional draft" to **market-standard, deployable product**.
> Grounded in a verified audit (2026-06-11) — every issue below was confirmed by execution
> or grep, not guesswork. Companion docs: [FRONTEND_PLAN.md](FRONTEND_PLAN.md) (feature spec),
> [APP_BUILD_STEPS.md](APP_BUILD_STEPS.md) (original build order), [PLATFORM_PLAN.md](PLATFORM_PLAN.md) (architecture).

---

## 0. Verified Current State (what's fixed vs. outstanding)

### ✅ Already fixed (verified 2026-06-11 — don't redo)
| Item | Status |
|---|---|
| `alert()` error popups | gone (0 usages) |
| Record endpoint event-loop crash | fixed (`async def record_test`) |
| DB session leak (`next(get_session())`) | fixed |
| Deprecated `@app.on_event` | migrated to `lifespan` |
| `datetime.utcnow()` deprecations | fixed (0 left) |
| `.db` files in git | ignored (`*.db`, `-shm`, `-wal`) |
| `display-font` undefined class | now defined in CSS |
| Crop screenshots static mount | `/projects` mount added |

### ❌ Outstanding (this plan)
| # | Issue | Evidence | Phase |
|---|---|---|---|
| 1 | **Invalid Tailwind shades** `slate-650/750/850` render as nothing → flat, surface-less UI | **77 usages** | P1 |
| 2 | **React Query installed, unused** — manual fetch/useEffect/setInterval in all 8 pages | grep: 0 usages | P2 |
| 3 | **Zustand installed, unused** — settings re-fetched per page on a 10s interval | grep: 0 usages | P2 |
| 4 | **react-router-dom installed, unused** — hand-rolled hash routing, string parsing | grep: 0 usages | P2 |
| 5 | **TanStack Table installed, unused** — hand-built tables, no sort/filter | grep: 0 usages | P3 |
| 6 | **No component primitives** — Tailwind class-soup duplicated across pages | no `components/` dir | P1 |
| 7 | **TS `strict` off**, `any` everywhere | tsconfig | P4 |
| 8 | **No error boundary** — render error = white screen | grep | P2 |
| 9 | **No toast system** — banners ad-hoc per page | — | P1 |
| 10 | **Brand/copy drift** — "Record Scraper Flow", "scraper plugin" in a *test* tool | NewTest.tsx etc. | P3 |
| 11 | **Theme tokens defined but unused** — hardcoded `bg-[#192233]` everywhere | index.css vs pages | P1 |
| 12 | **No frontend tests** (no Vitest/RTL) | — | P4 |
| 13 | **CI has no frontend job** — broken build can merge | ci.yml is Python-only | P5 |
| 14 | **No env-based API config** — `API_BASE=''` breaks Vite dev for downloads/WS | api.ts | P2 |
| 15 | **Icon-only buttons lack aria-labels**; portal never run through its own a11y check | TestDetail.tsx | P3 |
| 16 | **Light/dark half-scaffolding** — invalid `.dark :root` selector, no toggle | index.css | P1 |
| 17 | **No deployment packaging** — frontend dist not bundled; no `scrapewizard start` | — | P5 |
| 18 | Stray `test_studio.db` in repo root (untracked but present) | ls | P5 |

---

## PHASE 1 — Design System Foundation *(1–2 days; biggest visual payoff)*

> Goal: the app *looks* designed. One source of truth for color/spacing/type; reusable
> primitives so every later fix is one edit, not 77.

### 1.1 Fix the color system (issue #1, #11, #16)
- In `studio/frontend/src/index.css` `@theme`, define the missing shades **and** semantic tokens:
  ```css
  @theme {
    --color-slate-650: #3e4c66;   /* legitimize existing usage instantly */
    --color-slate-750: #2c3a52;
    --color-slate-850: #16202f;
    --color-surface:  #192233;    /* card/panel background */
    --color-surface-2:#1e2a40;    /* raised surface */
    --color-edge:     #324467;    /* borders */
    --color-accent:   #135bec;
    --color-pass: #10b981;  --color-fail: #f43f5e;
    --color-warn: #f59e0b;  --color-run:  #3b82f6;
  }
  ```
  Defining `slate-650/750/850` makes all 77 broken classes render **immediately** with zero
  page edits — then migrate to semantic names (`bg-surface`, `border-edge`) opportunistically
  as pages are touched in Phase 2.
- Remove the dead `.dark :root` block; commit to **dark-only** for v1 (decision, not accident).
- ✔️ Every card/panel has a visible surface + border; no `bg-[#hex]` hardcodes left in pages.

### 1.2 Build the component primitives (issue #6, #9)
Create `studio/frontend/src/components/ui/`:

| Component | Notes |
|---|---|
| `Button` | variants: primary / secondary / ghost / danger; sizes; `loading` prop; auto `aria-busy` |
| `Card` | surface + border + padding; header/footer slots |
| `Input`, `Select`, `Label` | consistent focus rings, error state |
| `Badge` / `StatusPill` | semantic statuses: passed/failed/running/queued/healed |
| `EmptyState` | icon + message + CTA (used by every list) |
| `LoadingSkeleton` | shimmer blocks for lists/cards |
| `ErrorState` | human message + retry + "copy details" |
| `Toast` + `useToast()` | success/error/info; replaces all ad-hoc banners (see 2.2 store) |
| `PageHeader` | title + breadcrumb + actions slot (fills the empty top bar) |
| `ConfirmDialog` | for deletes (currently un-confirmed) |

- ✔️ One Storybook-style demo route (`/dev/ui`, dev-only) rendering all primitives — your
  visual regression target later.

---

## PHASE 2 — Modern Data & App Architecture *(2–3 days; the "market standard" core)*

> Goal: actually use the stack you ship. Server state via React Query, client state via
> Zustand, real routing, resilient errors.

### 2.1 React Query data layer (issue #2)
- Wrap app in `QueryClientProvider` (sane defaults: `staleTime: 15s`, `retry: 1`).
- Create `src/hooks/` — one typed hook per resource, **delete all manual fetch/useEffect**:
  - `useSettings()` / `useUpdateSettings()` / `useTestConnection()`
  - `useTests()` / `useTest(id)` / `useCreateTest()` / `useUpdateTest(id)` / `useDeleteTest(id)`
  - `useRecordStatus(id)` — `refetchInterval: 1000` *only while recording* (replaces hand-rolled `setInterval`)
  - `useTriggerRun(id)` / `useRun(runId)` / `useRuns(filters)` / `useStats()`
- Mutations invalidate their queries (`onSuccess: invalidate(['tests'])`) → no manual reloads.
- Keep the **WebSocket** in RunDetail (it's correct); use it to patch the `useRun` cache via
  `queryClient.setQueryData` so live + fetched state stay consistent.
- ✔️ grep shows zero raw `fetch(` outside `lib/api.ts`; zero `setInterval` outside the WS fallback.

### 2.2 Zustand app store (issue #3, #9)
- `src/store/app.ts`: `{ settings, setSettings, toasts, pushToast, dismissToast }`.
- Settings loaded **once** via `useSettings()`, mirrored to the store for the AI pill —
  delete the 10-second polling in `App.tsx`.
- ✔️ AI pill updates instantly after saving Settings (cache invalidation), no polling.

### 2.3 Real routing (issue #4)
- Replace hand-rolled hash state with **`createHashRouter`** (react-router v7) — keeps
  compatibility with the FastAPI static mount (no server rewrites needed), but gives
  `useParams`, `useNavigate`, layout routes, and a 404 route.
- Layout route renders Sidebar + `PageHeader` + `<Outlet/>`.
- ✔️ Deep links (`#/tests/3`, `#/runs/7`) load correctly on hard refresh from the prod mount.

### 2.4 Error resilience & API config (issue #8, #14)
- `ErrorBoundary` component at the layout level → renders `ErrorState`, not a white screen.
- `src/lib/config.ts`: `export const API_BASE = import.meta.env.VITE_API_BASE ?? ''` —
  `.env.development` sets `VITE_API_BASE=http://127.0.0.1:8000`; prod stays `''`.
  Use it for **fetch, file downloads (export), artifact image URLs, and the WS URL**
  (`ws://` derived from API_BASE or `location` in prod).
- Vite dev proxy alternative documented in `vite.config.js` (either works; pick one).
- ✔️ `npm run dev` against a running backend: every feature works, including pytest export
  download and screenshots.

### 2.5 Page migration order (each page shrinks as it moves onto the foundation)
1. **Settings** (simplest — proves the pattern)
2. **Tests list** (+ `EmptyState`, `ConfirmDialog` for delete)
3. **NewTest / recording** (uses `useRecordStatus` polling hook)
4. **TestDetail / Step Manager** (largest; keep local edit state, save via mutation)
5. **RunDetail** (React Query + WS cache patching)
6. **Dashboard + RunHistory** (swap hand tables for TanStack Table — sort/filter free)
- ✔️ After each page: it works, it's shorter, and it uses zero ad-hoc fetch/state.

---

## PHASE 3 — Product Polish & UX *(1–2 days)*

### 3.1 Rebrand the copy (issue #10)
- Sweep all UI strings: "Record Scraper Flow" → "Record Test Flow"; "scraper plugin" →
  "test"; placeholder "Scrape products list" → "Login flow smoke test"; sidebar
  "Test Suite" ✓ (already right). Keep "ScrapeWizard" as brand until the §18 name decision.
- ✔️ grep for "scrap" in `studio/frontend/src` returns only the brand name.

### 3.2 Make evidence visible
- **Step crop thumbnails** in Step Manager via the new `/projects` mount (already exists
  backend-side) — render `<img>` with lightbox; placeholder if missing.
- **Visual diff viewer** in RunDetail: baseline / current / diff tabs when
  `visual_diff_score > 0`.
- ✔️ A recorded step shows its element crop; a visually-changed run shows the diff.

### 3.3 Accessibility & ergonomics (issue #15)
- `aria-label` on all icon-only buttons (move/delete/etc.); focus-visible rings (primitives
  give this for free).
- Keyboard: `r` = run (on TestDetail), `/` = focus search (Tests), `Esc` = close dialogs.
- **Self-a11y check:** Playwright script loads the built portal and runs our own
  `perform_a11y_check` against each route → wire into CI (Phase 5). *We ship an a11y
  checker; we must pass it.*
- ✔️ Portal passes its own axe scan with 0 serious/critical violations.

### 3.4 The four UI states, audited
- Walk every page against the checklist: **empty / loading / error / partial** (FRONTEND_PLAN §2).
  Primitives make this mostly drop-in. Partial = mid-run refresh of RunDetail recovers from
  `GET /runs/{id}` + WS.
- ✔️ Kill the dev server mid-action; every page degrades to a designed state, never a blank div.

---

## PHASE 4 — Type Safety & Tests *(1–2 days)*

### 4.1 TypeScript strict (issue #7)
- `"strict": true` in tsconfig; fix fallout (mostly `err: any` → `unknown` + narrow,
  `interval: any` → `ReturnType<typeof setInterval>`).
- Shared API types: one `src/lib/types.ts` matching backend models (`Test`, `Step`, `Run`,
  `StepResult`, `Settings`) — the API client and hooks are fully typed end-to-end.
- ✔️ `tsc --noEmit` clean.

### 4.2 Frontend tests (issue #12)
- **Vitest + React Testing Library + MSW** (mock the API):
  - primitives render-tests (Button states, EmptyState, Toast)
  - Settings: load → edit → save (mutation called, toast shown)
  - Tests list: empty state CTA, delete confirm flow
  - TestDetail: edit selector → save payload shape correct
  - RunDetail: WS message updates a step to failed
- ✔️ `npm test` green; meaningful coverage on the 3 critical pages (not a % target — the flows above).

### 4.3 Backend contract tests (top-up)
- Extend `tests/integration/test_studio_backend.py`: export endpoint returns a runnable file;
  `/stats` shape; run executor error path writes `status="error"`.
- ✔️ pytest suite green (currently 4 studio tests → ~8).

---

## PHASE 5 — CI/CD, Packaging & Deployment *(1–2 days)*

### 5.1 Frontend CI job (issue #13)
Add to `.github/workflows/ci.yml`:
```yaml
frontend:
  runs-on: ubuntu-latest
  defaults: { run: { working-directory: studio/frontend } }
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with: { node-version: 22, cache: npm, cache-dependency-path: studio/frontend/package-lock.json }
    - run: npm ci
    - run: npm run lint
    - run: npx tsc --noEmit
    - run: npm test -- --run
    - run: npm run build
```
Plus the **self-a11y job** (3.3) after build. ✔️ A broken frontend can no longer merge.

### 5.2 Ship as one installable package (issue #17)
- **Build pipeline:** CI builds `studio/frontend/dist` → included in the wheel as package
  data (`[tool.setuptools.package-data]` + move/copy dist under `scrapewizard/studio_static/`
  or add `studio*` to packages). Users need **no Node**.
- **`scrapewizard start` command:** init DB → uvicorn on `127.0.0.1:<free port>` → serve the
  bundled dist → `webbrowser.open()`. (Backend already mounts dist when present.)
- **`scrapewizard doctor`** extended: check Playwright browsers; offer `playwright install chromium`.
- **Versioning:** single source (`pyproject.toml`) → exposed at `/health` and in the sidebar
  (currently hardcoded "1.2.0" in three places).
- ✔️ On a clean machine: `pipx install <wheel>` → `scrapewizard start` → browser opens →
  record → run → report. No Node, no manual uvicorn.

### 5.3 Release flow
- Extend the existing tag-triggered `release.yml`: build frontend → build wheel → attach to
  GitHub Release → (when named/ready) publish to PyPI.
- `CHANGELOG.md` started; Conventional Commits already in use.
- Delete stray `test_studio.db` from the working tree (issue #18); point tests at tmp DBs.
- ✔️ Tagging `v1.3.0` produces an installable artifact with the UI bundled.

### 5.4 Deployment docs
- README "Run the Studio" section: `pipx install … && scrapewizard start` + screenshot/GIF.
- `SECURITY.md` note: server binds localhost-only by design; not a hosted service.
- ✔️ A stranger can install and reach the dashboard in < 5 minutes from README alone.

---

## PHASE 6 — Launch Gate (condensed pre-flight)

- [ ] Fresh-machine install → record → edit → run → report on Win/macOS/Linux (CI matrix + one manual)
- [ ] All Phase 1–5 acceptance checks green
- [ ] Portal passes self-a11y; zero invalid Tailwind classes (`grep slate-[678]50` = only @theme defs)
- [ ] `tsc --noEmit`, lint, vitest, pytest, build — all green in CI
- [ ] Copy sweep done (no "scraper" strings in the test UI)
- [ ] Demo GIF recorded (record → break page → run → failure evidence)
- [ ] Version bumped once in pyproject; visible in UI + `/health`

---

## Execution order & effort summary

| Phase | What | Effort | Visible result |
|---|---|---|---|
| **P1** | Color system + primitives | 1–2 d | App suddenly looks designed |
| **P2** | React Query + Zustand + Router + page migrations | 2–3 d | Modern, resilient, fast |
| **P3** | Copy rebrand + evidence UI + a11y + states | 1–2 d | Feels like a product |
| **P4** | TS strict + tests | 1–2 d | Trustworthy to change |
| **P5** | CI + packaging + `start` | 1–2 d | **Deployable** |
| **P6** | Launch gate | ½ d | Ship |

**Total: ~7–11 focused days.** P1 → P2 are sequential (primitives before migrations);
P3/P4 can interleave; P5 last (packages whatever exists).

> **Single highest-leverage first step:** Phase 1.1 — the three `@theme` lines that fix all
> 77 invalid color classes at once. Fifteen minutes, transforms the entire app's appearance.
