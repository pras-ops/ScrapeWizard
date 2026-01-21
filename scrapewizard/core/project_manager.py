import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
from scrapewizard.core.state import State
from scrapewizard.core.logging import log

class ProjectManager:
    """Manages project directory creation, loading, and state persistence."""

    PROJECTS_ROOT = Path.home() / "scrapewizard_projects"

    @classmethod
    def ensure_root(cls):
        cls.PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def create_project(cls, url: str) -> Dict:
        """Create a new project directory and initialize session."""
        cls.ensure_root()
        
        # Extract domain for friendlier name
        domain = url.split("//")[-1].split("/")[0].replace("www.", "").replace(".", "_")
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M")
        project_name = f"project_{domain}_{timestamp}"
        project_dir = cls.PROJECTS_ROOT / project_name
        
        # Ensure unique directory
        if project_dir.exists():
             project_name = f"{project_name}_{str(uuid.uuid4())[:4]}"
             project_dir = cls.PROJECTS_ROOT / project_name
             
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (project_dir / "logs").mkdir()
        (project_dir / "llm_logs").mkdir()
        (project_dir / "output").mkdir()

        # Initialize Session
        session_data = {
            "project_id": project_name,
            "created_at": datetime.now().isoformat(),
            "url": url,
            "state": State.INIT.value,
            "project_dir": str(project_dir),
            "history": []
        }
        
        cls.save_state(project_dir, session_data)
        log(f"Created project at: {project_dir}")
        return session_data

    @classmethod
    def load_project(cls, project_dir_path: str) -> Optional[Dict]:
        """Load session state from a project directory."""
        path = Path(project_dir_path) / "session.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"Failed to load project: {e}", level="error")
            return None

    @classmethod
    def save_state(cls, project_dir: Path, session_data: Dict):
        """Save session state to disk."""
        if isinstance(project_dir, str):
            project_dir = Path(project_dir)
            
        with open(project_dir / "session.json", "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

    @classmethod
    def list_projects(cls):
        """List all available projects sorted by creation time."""
        if not cls.PROJECTS_ROOT.exists():
            return []
            
        projects = []
        for p in cls.PROJECTS_ROOT.iterdir():
            if p.is_dir() and (p / "session.json").exists():
                projects.append(p)
        
        return sorted(projects, key=lambda x: x.stat().st_mtime, reverse=True)
