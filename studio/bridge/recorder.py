import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

class SessionRecorder:
    """Records CDP events and user actions for Studio replay and AET compilation."""
    
    def __init__(self, session_id: str, output_dir: Optional[Path] = None):
        self.session_id = session_id
        self.output_dir = output_dir or Path("studio/recordings")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.output_dir / f"{session_id}.jsonl"
    
    def record_event(self, event_type: str, data: Dict[str, Any]):
        """Save an event to the session log."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        }
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def get_file_path(self) -> Path:
        return self.file_path
