from pathlib import Path
from scrapewizard.core.config import ConfigManager

# Re-export get_session for convenience
from studio.backend.db import get_session

# Root path for all studio execution screenshots and diff outputs
STUDIO_ARTIFACTS_DIR = Path.home() / ".scrapewizard" / "artifacts"
STUDIO_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# Shared stable path for visual test baselines
STUDIO_BASELINES_DIR = Path.home() / ".scrapewizard" / "baselines"
STUDIO_BASELINES_DIR.mkdir(parents=True, exist_ok=True)
