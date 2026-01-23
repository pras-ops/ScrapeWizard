import json
import csv
from pathlib import Path
from typing import List, Dict, Any

def write_json(data: List[Dict[str, Any]], filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def write_csv(data: List[Dict[str, Any]], filepath: Path):
    if not data:
        return
    filepath.parent.mkdir(parents=True, exist_ok=True)
    keys = data[0].keys()
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)

def write_excel(data: List[Dict[str, Any]], filepath: Path):
    # Fallback to CSV if pandas/openpyxl not available for simplicity in runtime
    # but normally we'd use pandas here.
    try:
        import pandas as pd
        df = pd.DataFrame(data)
        df.to_excel(filepath, index=False)
    except ImportError:
        csv_path = filepath.with_suffix(".csv")
        write_csv(data, csv_path)
