"""The recipe data model, with loading, saving and validation."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

from scrapewizard.recipe.types import FIELD_TYPES

FETCH_MODES = ("http", "browser")
# next_link / auto move to a new address; load_more and scroll grow the page in a browser.
PAGINATION_TYPES = ("none", "next_link", "auto", "load_more", "scroll")
IN_PLACE_PAGINATION = ("load_more", "scroll")


class RecipeError(ValueError):
    """A recipe file is missing something or has an invalid value."""


@dataclass
class Field:
    """One value to read from each item.

    ``select`` is a list of selectors tried in order. Each is CSS relative to
    the item, optionally ending in ``@attr`` to read an attribute instead of
    the text. ``@attr`` alone reads an attribute of the item itself, and an
    empty string reads the item's own text.
    """
    name: str
    select: List[str]
    type: str = "text"


@dataclass
class Recipe:
    name: str
    url: str
    container: str
    fields: List[Field]
    fetch: str = "http"
    pagination: Dict[str, Any] = field(default_factory=lambda: {"type": "none"})
    checks: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)  # repairs made, oldest first

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "name": self.name,
            "url": self.url,
            "fetch": self.fetch,
            "collection": {
                "container": self.container,
                "fields": {f.name: {"select": list(f.select), "type": f.type} for f in self.fields},
            },
            "pagination": dict(self.pagination),
            "checks": dict(self.checks),
        }
        if self.history:
            data["history"] = [dict(entry) for entry in self.history]
        return data


def recipe_from_dict(data: Any) -> Recipe:
    """Validate a parsed recipe and return it. Raises RecipeError with a plain message."""
    if not isinstance(data, dict):
        raise RecipeError("A recipe must be a mapping with name, url and collection.")
    for key in ("name", "url", "collection"):
        if not data.get(key):
            raise RecipeError(f"The recipe is missing '{key}'.")

    collection = data["collection"]
    if not isinstance(collection, dict) or not collection.get("container"):
        raise RecipeError("'collection' needs a 'container' selector.")
    raw_fields = collection.get("fields")
    if not isinstance(raw_fields, dict) or not raw_fields:
        raise RecipeError("'collection.fields' needs at least one field.")

    fields = []
    for name, spec in raw_fields.items():
        if isinstance(spec, str):
            spec = {"select": [spec]}
        if not isinstance(spec, dict) or "select" not in spec:
            raise RecipeError(f"Field '{name}' needs a 'select' entry.")
        select = spec["select"]
        select = [select] if isinstance(select, str) else list(select)
        if not all(isinstance(s, str) for s in select) or not select:
            raise RecipeError(f"Field '{name}': 'select' must be a selector or a list of selectors.")
        field_type = spec.get("type", "text")
        if field_type not in FIELD_TYPES:
            raise RecipeError(f"Field '{name}': unknown type '{field_type}'. Use one of: {', '.join(FIELD_TYPES)}.")
        fields.append(Field(name=str(name), select=select, type=field_type))

    fetch = data.get("fetch", "http")
    if fetch not in FETCH_MODES:
        raise RecipeError(f"'fetch' must be one of: {', '.join(FETCH_MODES)}.")

    pagination = data.get("pagination") or {"type": "none"}
    if not isinstance(pagination, dict) or pagination.get("type", "none") not in PAGINATION_TYPES:
        raise RecipeError(f"'pagination.type' must be one of: {', '.join(PAGINATION_TYPES)}.")

    checks = data.get("checks") or {}
    if not isinstance(checks, dict):
        raise RecipeError("'checks' must be a mapping.")

    history = data.get("history") or []
    if not isinstance(history, list) or not all(isinstance(entry, dict) for entry in history):
        raise RecipeError("'history' must be a list of entries.")

    return Recipe(
        name=str(data["name"]),
        url=str(data["url"]),
        container=str(collection["container"]),
        fields=fields,
        fetch=fetch,
        pagination=dict(pagination),
        checks=dict(checks),
        history=[{str(k): str(v) for k, v in entry.items()} for entry in history],
    )


def load_recipe(path: Union[str, Path]) -> Recipe:
    path = Path(path)
    if not path.exists():
        raise RecipeError(f"Recipe file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise RecipeError(f"{path} is not valid YAML: {e}") from e
    return recipe_from_dict(data)


def save_recipe(recipe: Recipe, path: Union[str, Path]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(recipe.to_dict(), sort_keys=False, allow_unicode=True, width=100)
    path.write_text(text, encoding="utf-8")
    return path
