"""What a recipe remembers about its last successful run.

The memory lives in ``.scrapewizard/<name>.state.json`` beside the recipe. It
is used to report what changed between runs and to check that a repair still
finds items that were there before.
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from scrapewizard.recipe.model import Recipe

STATE_DIR = ".scrapewizard"
SAMPLE_SIZE = 50  # full records kept, for checking repairs


@dataclass
class Changes:
    new: int
    changed: int
    removed: int

    def __str__(self) -> str:
        return f"{self.new} new, {self.changed} changed, {self.removed} removed since last run"


def state_path(recipe_path: Union[str, Path]) -> Path:
    """shop.recipe.yaml -> .scrapewizard/shop.state.json in the same folder."""
    recipe_path = Path(recipe_path)
    name = recipe_path.name
    for ending in (".recipe.yaml", ".recipe.yml", ".yaml", ".yml"):
        if name.endswith(ending):
            name = name[: -len(ending)]
            break
    return recipe_path.parent / STATE_DIR / f"{name}.state.json"


def key_field(recipe: Recipe, records: List[Dict[str, Any]]) -> Optional[str]:
    """The field that best tells records apart: a link if unique, else a well-filled text field."""
    if not records:
        return None

    def uniqueness(name: str) -> float:
        values = [str(r[name]) for r in records if r.get(name) is not None]
        return len(set(values)) / len(records) if values else 0.0

    ordered = sorted(recipe.fields, key=lambda f: (f.type != "url", f.name != "title"))
    for f in ordered:
        if f.type in ("image", "money", "number"):
            continue
        if uniqueness(f.name) >= 0.9:
            return f.name
    return None


def _row_hash(record: Dict[str, Any]) -> str:
    text = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def make_state(recipe: Recipe, records: List[Dict[str, Any]], pages: int) -> Dict[str, Any]:
    key = key_field(recipe, records)
    total = len(records) or 1
    return {
        "version": 1,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(records),
        "pages": pages,
        "key": key,
        "fill": {f.name: round(sum(1 for r in records if r.get(f.name) is not None) / total, 3)
                 for f in recipe.fields},
        "index": {str(r[key]): _row_hash(r) for r in records if r.get(key) is not None} if key else {},
        "sample": records[:SAMPLE_SIZE],
    }


def save_state(recipe_path: Union[str, Path], recipe: Recipe, records: List[Dict[str, Any]], pages: int) -> Path:
    path = state_path(recipe_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(make_state(recipe, records, pages), ensure_ascii=False, default=str),
                    encoding="utf-8")
    return path


def load_state(recipe_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    path = state_path(recipe_path)
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None  # unreadable memory is treated as no memory
    return state if isinstance(state, dict) and state.get("version") == 1 else None


def compare(state: Optional[Dict[str, Any]], records: List[Dict[str, Any]], pages: int) -> Optional[Changes]:
    """Count new, changed and removed records since the remembered run.

    ``pages`` is the page limit the run was asked for (not the pages it
    happened to read), so two "all pages" runs compare even if the site grew.

    Returns None when a fair comparison is not possible: no memory, no field
    that identifies a record, or a different page limit.
    """
    if not state or not state.get("key") or state.get("pages") != pages:
        return None
    key = state["key"]
    before: Dict[str, str] = state.get("index") or {}
    now = {str(r[key]): _row_hash(r) for r in records if r.get(key) is not None}
    if not before or not now:
        return None
    return Changes(
        new=sum(1 for k in now if k not in before),
        changed=sum(1 for k, h in now.items() if k in before and before[k] != h),
        removed=sum(1 for k in before if k not in now),
    )
