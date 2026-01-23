import json
from pathlib import Path

def load_storage_state(project_dir: Path):
    storage_path = project_dir / "storage_state.json"
    if storage_path.exists():
        return str(storage_path)
    return None
