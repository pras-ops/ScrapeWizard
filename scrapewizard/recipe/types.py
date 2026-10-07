"""Value typing: recognise what a scraped value is, and clean it for export."""
import re
from typing import Any, List, Optional
from urllib.parse import urljoin

FIELD_TYPES = ("text", "url", "image", "money", "number", "date", "email")

_CURRENCY = r"(?:[$€£¥₹₩₽]|USD|EUR|GBP|INR|JPY|CAD|AUD|Rs\.?)"
MONEY_RE = re.compile(rf"^(?:{_CURRENCY}\s?-?\d[\d.,]*|-?\d[\d.,]*\s?{_CURRENCY})$", re.I)
NUMBER_RE = re.compile(r"^-?\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?$|^-?\d+(?:\.\d+)?$")
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
DATE_RE = re.compile(
    rf"^(?:\d{{4}}-\d{{2}}-\d{{2}}(?:[T ]\d{{2}}:\d{{2}}(?::\d{{2}})?.*)?"   # 2024-01-31[T10:00]
    rf"|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}"                                # 31/01/2024
    rf"|{_MONTH}\.?\s+\d{{1,2}},?\s+\d{{4}}"                                   # Jan 31, 2024
    rf"|\d{{1,2}}\s+{_MONTH}\.?,?\s+\d{{4}})$",                                # 31 January 2024
    re.I,
)


def clean_text(value: Any) -> str:
    """Collapse whitespace; None becomes an empty string."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def infer_type(values: List[str]) -> str:
    """Pick the type most sample values agree on (at least 60%), else text."""
    samples = [clean_text(v) for v in values if clean_text(v)]
    if not samples:
        return "text"
    for name, pattern in (("money", MONEY_RE), ("email", EMAIL_RE), ("date", DATE_RE), ("number", NUMBER_RE)):
        hits = sum(1 for v in samples if pattern.match(v))
        if hits / len(samples) >= 0.6:
            return name
    return "text"


def convert(value: Optional[str], field_type: str, base_url: str = "") -> Any:
    """Clean one extracted value according to its field type.

    Empty values become None so that coverage checks can count them. Money
    and dates are kept as cleaned text: converting them would lose the
    currency or guess at an ambiguous date format.
    """
    text = clean_text(value)
    if not text:
        return None
    if field_type in ("url", "image"):
        return urljoin(base_url, text) if base_url else text
    if field_type == "number":
        compact = text.replace(",", "").replace(" ", "")
        try:
            number = float(compact)
        except ValueError:
            return text
        return int(number) if number.is_integer() and "." not in compact else number
    return text
