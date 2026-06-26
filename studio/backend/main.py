import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add project root to sys.path to resolve scrapewizard imports correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scrapewizard.core.logging import log
from studio.backend.db import init_db
from studio.backend.deps import STUDIO_ARTIFACTS_DIR
from studio.backend.routes_settings import router as settings_router
from studio.backend.routes_tests import router as tests_router
from studio.backend.routes_runs import router as runs_router

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    log("Initializing SQLite database on startup...")
    init_db()
    yield

app = FastAPI(title="ScrapeWizard Studio Backend", version="1.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    """Health check endpoint containing engine version details."""
    return {"status": "ok", "version": "1.2.0", "engine": "ScrapeWizard-Studio"}

# Register Settings, Tests and Runs routers
app.include_router(settings_router)
app.include_router(tests_router)
app.include_router(runs_router)

from scrapewizard.core.config import ConfigManager

# Mount artifacts folder to serve screenshots and visual diff crops
STUDIO_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=str(STUDIO_ARTIFACTS_DIR)), name="artifacts")

# Mount projects folder to serve recorded step crop screenshots
projects_dir = ConfigManager.CONFIG_DIR / "projects"
projects_dir.mkdir(parents=True, exist_ok=True)
app.mount("/projects", StaticFiles(directory=str(projects_dir)), name="projects")

# Mount React static frontend dist output (prod bundle)
frontend_dist = Path(__file__).parent / ".." / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    log("React frontend dist bundle not found; serving API endpoints only.", level="warning")

if __name__ == "__main__":
    import uvicorn
    # Bound to local loopback interface only for secure local operation
    uvicorn.run(app, host="127.0.0.1", port=8000)
