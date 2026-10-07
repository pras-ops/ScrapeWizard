"""Repair a recipe after a site changed, and check the repair against known data.

A scraper has something to check a repair against: the records it produced
last time. The page is searched again for a repeating block, the recipe's
fields are matched to the new block by comparing values with remembered
records, and the repair counts as verified only if known items are found again.
"""
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from scrapewizard.recipe.builder import MIN_ITEMS, candidate_recipe, rank_candidates
from scrapewizard.recipe.embedded import DATA_PREFIX, find_lists
from scrapewizard.recipe.extract import DEFAULT_REQUIRED_COVERAGE, extract_records, parse
from scrapewizard.recipe.model import Field, Recipe

MAX_CANDIDATES_TRIED = 8
MAX_EXAMPLES = 6
# Share of remembered rows that must be found again for a repair to count as verified.
VERIFIED_SHARE = 0.2


class RepairRefused(Exception):
    """No safe repair was found. The message says why and is safe to show."""


@dataclass
class Repair:
    recipe: Recipe
    changes: List[str]             # "price: span.cost -> span.amount"
    verified: bool                 # remembered items were found again
    matched: int                   # how many remembered items were found
    records: List[Dict[str, Any]]  # what the repaired recipe yields on the page


def _coverage(records: List[Dict[str, Any]], name: str) -> float:
    return sum(1 for r in records if r.get(name) is not None) / len(records) if records else 0.0


def what_broke(records: List[Dict[str, Any]], recipe: Recipe, state: Optional[Dict[str, Any]]) -> Optional[str]:
    """A plain sentence if the run looks broken by a site change, else None."""
    if not records:
        return "No records were found."
    total = len(records)
    needed = float(recipe.checks.get("required_coverage", DEFAULT_REQUIRED_COVERAGE))
    for name in recipe.checks.get("required", []) or []:
        if _coverage(records, name) < needed:
            filled = sum(1 for r in records if r.get(name) is not None)
            return f'"{name}" stopped matching ({filled} of {total} rows).'
    for name, before in ((state or {}).get("fill") or {}).items():
        # A field that used to be nearly always filled and now mostly isn't.
        if before >= 0.9 and any(f.name == name for f in recipe.fields) and _coverage(records, name) < 0.5:
            filled = sum(1 for r in records if r.get(name) is not None)
            return f'"{name}" stopped matching ({filled} of {total} rows).'
    return None


def _values(records: List[Dict[str, Any]], name: str) -> List[Optional[str]]:
    return [None if r.get(name) is None else str(r[name]) for r in records]


def _pair_rows(old: List[Dict[str, Any]], new: List[Dict[str, Any]],
               old_fields: List[str], new_fields: List[str]) -> List[Tuple[int, int]]:
    """Pair remembered rows with rows found now, via the pair of fields sharing most values."""
    best: List[Tuple[int, int]] = []
    for o in old_fields:
        old_index: Dict[str, int] = {}
        for i, value in enumerate(_values(old, o)):
            if value is not None and value not in old_index:
                old_index[value] = i
        if len(old_index) < 2:
            continue
        for n in new_fields:
            pairs = []
            used = set()
            for j, value in enumerate(_values(new, n)):
                i = old_index.get(value) if value is not None else None
                if i is not None and i not in used:
                    used.add(i)
                    pairs.append((i, j))
            if len(pairs) > len(best):
                best = pairs
    return best


def _map_fields(recipe: Recipe, found: Recipe, sample: List[Dict[str, Any]],
                records: List[Dict[str, Any]]) -> Tuple[Dict[str, Field], int, int]:
    """Match each recipe field to a field of the block found now.

    Returns (mapping by old field name, rows paired with remembered rows,
    fields matched by comparing values).
    """
    old_names = [f.name for f in recipe.fields]
    new_by_name = {f.name: f for f in found.fields}
    pairs = _pair_rows(sample, records, old_names, list(new_by_name)) if sample else []

    mapping: Dict[str, Field] = {}
    by_data = 0
    if pairs:
        needed = max(2, int(0.3 * len(pairs)))
        scored = []
        for old in recipe.fields:
            for new in found.fields:
                agree = sum(
                    1 for i, j in pairs
                    if sample[i].get(old.name) is not None and str(sample[i][old.name]) == str(records[j].get(new.name))
                )
                if agree >= needed:
                    scored.append((agree, old.name, new.name))
        taken = set()
        for agree, old_name, new_name in sorted(scored, reverse=True):
            if old_name not in mapping and new_name not in taken:
                mapping[old_name] = new_by_name[new_name]
                taken.add(new_name)
                by_data += 1

    # Values that changed everywhere (prices) cannot be matched by data: fall back to name and type.
    taken_names = {f.name for f in mapping.values()}
    for old in recipe.fields:
        candidate = new_by_name.get(old.name)
        if old.name not in mapping and candidate is not None and candidate.name not in taken_names \
                and candidate.type == old.type:
            mapping[old.name] = candidate
            taken_names.add(candidate.name)
    return mapping, len(pairs), by_data


def _examples(recipe: Recipe, sample: List[Dict[str, Any]]) -> List[str]:
    """Remembered visible values that identify the list (titles, names), to find it again."""
    for f in sorted(recipe.fields, key=lambda f: f.name != "title"):
        if f.type != "text":
            continue
        values = [str(r[f.name]) for r in sample if r.get(f.name)]
        if len(set(values)) >= max(2, int(0.8 * len(values))):
            return list(dict.fromkeys(values))[:MAX_EXAMPLES]
    return []


def repair(recipe: Recipe, html: str, url: str, state: Optional[Dict[str, Any]]) -> Repair:
    """Find the recipe's data on the changed page and return a repaired recipe.

    Raises:
        RepairRefused: when no block on the page can be matched to the recipe
            with confidence. Nothing is guessed.
    """
    soup = parse(html)
    sample = (state or {}).get("sample") or []
    required = list(recipe.checks.get("required", []) or [])

    examples = _examples(recipe, sample) if sample else []
    candidates = rank_candidates(soup, examples) if sample else []
    if not candidates:
        candidates = rank_candidates(soup)  # remembered items are gone, or there is no memory
    options = [candidate_recipe(c, soup, url, recipe.name, recipe.fetch)[0] for c in candidates[:MAX_CANDIDATES_TRIED]]
    # Lists in the page's embedded data: where a "data:" recipe's list will have moved to,
    # and the only place to look on a page that JavaScript draws.
    in_data = find_lists(soup, examples) or find_lists(soup)
    from_data = [Recipe(name=recipe.name, url=url, container=container, fields=fields, fetch=recipe.fetch)
                 for container, fields in in_data[:MAX_CANDIDATES_TRIED]]
    options = from_data + options if recipe.container.startswith(DATA_PREFIX) else options + from_data
    if not options:
        raise RepairRefused("no repeating list was found on the page")

    best: Optional[Tuple[Tuple[int, int, int], Repair]] = None
    for found in options:
        found_records = extract_records(soup, found, url)
        if len(found_records) < MIN_ITEMS:
            continue
        mapping, paired, by_data = _map_fields(recipe, found, sample, found_records)
        if any(name not in mapping for name in required):
            continue
        verified = paired >= max(2, int(VERIFIED_SHARE * min(len(sample), len(found_records))))
        if not verified and len(mapping) < len(recipe.fields):
            continue  # without known data to check against, every field must match by name and type

        fields = []
        changes = []
        if found.container != recipe.container:
            changes.append(f"list: {recipe.container} -> {found.container}")
        for old in recipe.fields:
            new = mapping.get(old.name)
            if new is None:
                fields.append(old)
                continue
            if new.select[0] != old.select[0]:
                changes.append(f"{old.name}: {old.select[0] or '(item text)'} -> {new.select[0] or '(item text)'}")
            # New selectors first; the old ones stay as fallbacks in case the site changes back.
            fields.append(Field(old.name, list(dict.fromkeys(new.select + old.select)), old.type))

        pagination = dict(recipe.pagination)
        if pagination.get("type") == "next_link" and found.pagination.get("select") != pagination.get("select"):
            pagination.update({k: v for k, v in found.pagination.items() if k != "max_pages"})
        repaired = Recipe(
            name=recipe.name, url=recipe.url, container=found.container, fields=fields, fetch=recipe.fetch,
            pagination=pagination, checks=dict(recipe.checks), history=list(recipe.history),
        )
        records = extract_records(soup, repaired, url)
        if len(records) < MIN_ITEMS or what_broke(records, repaired, None):
            continue
        result = Repair(repaired, changes, verified, paired, records)
        rank = (int(verified), len(mapping), paired)
        if best is None or rank > best[0]:
            best = (rank, result)

    if best is None:
        raise RepairRefused("no list on the page could be matched to the recipe's fields")
    result = best[1]
    if not result.changes:
        raise RepairRefused("the page matches the recipe's selectors, so the data itself seems to be missing")
    result.recipe.history.append({
        "date": date.today().isoformat(),
        "repair": "; ".join(result.changes),
        "checked": f"{result.matched} known items found again" if result.verified else "not checked against earlier data",
    })
    return result
