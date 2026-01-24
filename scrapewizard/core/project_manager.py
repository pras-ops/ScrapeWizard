import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from scrapewizard.core.state import State
from scrapewizard.core.logging import log
from scrapewizard.utils.file_io import safe_read_json, safe_write_json

class ProjectManager:
    """Manages project directory creation, loading, and state persistence.
    
    This class handles the lifecycle of a scraping project, including creating
    directories, saving session state, and listing previous projects.
    """

    PROJECTS_ROOT = Path.home() / "scrapewizard_projects"

    @classmethod
    def ensure_root(cls) -> None:
        """Ensures the root projects directory exists."""
        cls.PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def create_project(cls, url: str) -> Dict[str, Any]:
        """Creates a new project directory and initializes the session.
        
        Args:
            url: The target URL to be scraped.
            
        Returns:
            A dictionary containing the initial session data.
        """
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
        (project_dir / "logs").mkdir(exist_ok=True)
        (project_dir / "llm_logs").mkdir(exist_ok=True)
        (project_dir / "output").mkdir(exist_ok=True)

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
    def load_project(cls, project_dir_path: str) -> Optional[Dict[str, Any]]:
        """Loads session state from a project directory.
        
        Args:
            project_dir_path: Path to the project directory.
            
        Returns:
            The session data dictionary if successful, None otherwise.
        """
        path = Path(project_dir_path) / "session.json"
        return safe_read_json(path, default=None)

    @classmethod
    def save_state(cls, project_dir: Path, session_data: Dict[str, Any]) -> None:
        """Saves session state to disk.
        
        Args:
            project_dir: Path to the project directory.
            session_data: The session data to save.
        """
        if isinstance(project_dir, str):
            project_dir = Path(project_dir)
            
        safe_write_json(project_dir / "session.json", session_data)

    @classmethod
    def list_projects(cls) -> List[Path]:
        """Lists all available projects sorted by creation time.
        
        Returns:
            A list of Paths to project directories.
        """
        if not cls.PROJECTS_ROOT.exists():
            return []
            
        projects = []
        for p in cls.PROJECTS_ROOT.iterdir():
            if p.is_dir() and (p / "session.json").exists():
                projects.append(p)
        
        return sorted(projects, key=lambda x: x.stat().st_mtime, reverse=True)
