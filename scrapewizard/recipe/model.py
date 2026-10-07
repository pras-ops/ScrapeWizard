"""The recipe data model, with loading, saving and validation."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
    # Item pages: ``follow`` names the list field holding each item's address, and
    # ``detail_fields`` are read from that page. Their selectors apply to the whole
    # page and may also be ``jsonld:path.to.key`` or ``meta:name``.
    follow: Optional[str] = None
    detail_fields: List[Field] = field(default_factory=list)
    # True if the pages are only visible when signed in. The saved sign-in lives
    # beside the recipe in .scrapewizard/, never in the recipe itself.
    login: bool = False

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
        if self.login:
            data["login"] = True
        if self.follow and self.detail_fields:
            data["detail"] = {
                "follow": self.follow,
                "fields": {f.name: {"select": list(f.select), "type": f.type} for f in self.detail_fields},
            }
        if self.history:
            data["history"] = [dict(entry) for entry in self.history]
        return data


def _parse_fields(raw_fields: Dict[str, Any]) -> List[Field]:
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
    return fields


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

    fields = _parse_fields(raw_fields)

    follow = None
    detail_fields: List[Field] = []
    detail = data.get("detail")
    if detail is not None:
        if not isinstance(detail, dict) or not detail.get("follow") or not isinstance(detail.get("fields"), dict):
            raise RecipeError("'detail' needs 'follow' (a field holding each item's address) and 'fields'.")
        follow = str(detail["follow"])
        if follow not in {f.name for f in fields}:
            raise RecipeError(f"'detail.follow' names '{follow}', which is not one of the list's fields.")
        detail_fields = _parse_fields(detail["fields"])

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
        follow=follow,
        detail_fields=detail_fields,
        login=bool(data.get("login", False)),
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
