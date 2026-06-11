# ScrapeWizard Studio — Frontend

The admin portal for the ScrapeWizard test automation platform (React + Vite).

**Status:** scaffold only — screens are not yet built. The portal UI/UX spec, screen list,
and build order live in [PLATFORM_PLAN.md](../../PLATFORM_PLAN.md) (§11 portal screens,
§19 design spec, Milestone M3).

## Development

```bash
npm install
npm run dev      # Vite dev server on http://localhost:5173
```

The backend API (FastAPI) runs separately on `http://127.0.0.1:8000`:

```bash
python studio/backend/main.py
```

CORS on the backend is restricted to the Vite dev origins (`localhost:5173` / `127.0.0.1:5173`).

## Planned structure (M3)

- React Router + React Query for data
- Component library: shadcn/ui (open decision §17 of PLATFORM_PLAN.md)
- Screens: Dashboard · Tests · Step Manager · Live Run · Run History/Reports · Settings
