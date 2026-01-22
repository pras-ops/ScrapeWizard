import json
import logging
import traceback
from pathlib import Path
from typing import Any, Optional
from scrapewizard.core.logging import log

logger = logging.getLogger(__name__)

def safe_read_json(path: Path, default: Any = None) -> Any:
    """
    Safely read a JSON file with robust error handling.
    """
    if default is None:
        default = {}
    
    try:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if not content.strip():
                return default
            return json.loads(content)
    except json.JSONDecodeError as e:
        log(f"Corrupted JSON in {path.name}: {e}", level="error")
    except PermissionError as e:
        log(f"Permission denied reading {path.name}: {e}", level="error")
    except OSError as e:
        log(f"IO error reading {path.name}: {e}", level="warning")
    except Exception as e:
        log(f"Unexpected error reading {path.name}: {traceback.format_exc()}", level="error")
    
    return default

def safe_write_json(path: Path, data: Any) -> bool:
    """
    Safely write data to a JSON file, ensuring parent directories exist.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except PermissionError as e:
        log(f"Permission denied writing to {path.name}: {e}", level="error")
    except OSError as e:
        log(f"IO error writing to {path.name}: {e}", level="error")
    except Exception as e:
        log(f"Unexpected error writing to {path.name}: {traceback.format_exc()}", level="error")
        raise
    
    return False
