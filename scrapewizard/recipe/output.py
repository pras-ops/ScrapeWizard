"""Saving records to a data file."""
import json
from pathlib import Path
from typing import Any, Dict, List

from scrapewizard_runtime.io import write_csv

FORMATS = ("csv", "json", "xlsx")


class OutputError(Exception):
    """The data could not be saved. The message is safe to show to the user."""


def save_records(records: List[Dict[str, Any]], path: Path, fmt: str) -> Path:
    """Write records to ``path`` in the given format and return the path."""
    if fmt not in FORMATS:
        raise OutputError(f"Unknown format '{fmt}'. Use one of: {', '.join(FORMATS)}.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv":
        write_csv(records, path)
    elif fmt == "json":
        path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        try:
            import pandas as pd
        except ImportError as e:
            raise OutputError("Excel export needs two extra packages: pip install pandas openpyxl") from e
        try:
            pd.DataFrame(records).to_excel(path, index=False)
        except ImportError as e:
            raise OutputError("Excel export needs one more package: pip install openpyxl") from e
    return path
