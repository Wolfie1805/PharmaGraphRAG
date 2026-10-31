"""
Normalization utilities for Phase 2 data processing.
Unicode standardization, quote-aware list splitting, artifact detection, and robust ISO date parsing.
"""

import csv
import io
import re
import unicodedata
from typing import List, Optional, Tuple, Dict, Any

MONTH_NAME_TO_NUM: Dict[str, str] = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}

SEASONS = {"spring", "summer", "fall", "autumn", "winter"}


def normalize_text(text: Optional[str]) -> str:
    """Normalize text using Unicode NFKC and strip leading/trailing whitespace."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFKC", str(text))
    return norm.strip()


def normalize_search_term(text: Optional[str]) -> str:
    """
    Produce normalized representation for indexing and matching.
    NFKC Unicode normalization, case-folding, and whitespace collapsing.
    """
    if not text:
        return ""
    norm = unicodedata.normalize("NFKC", str(text)).casefold()
    # Collapse multiple whitespaces
    norm = re.sub(r"\s+", " ", norm)
    # Strip enclosing quotes if any
    norm = norm.strip("\"'")
    return norm.strip()


def parse_pubmed_date(
    year: Optional[str],
    month: Optional[str],
    day: Optional[str],
    medline_date: Optional[str]
) -> Tuple[str, str]:
    """
    Parse PubMed date parts into (pubdate_iso, date_precision).
    Date precision is one of: 'year', 'month', 'day'.
    Seasons are NEVER mapped to arbitrary calendar months; precision is kept at 'year'.
    """
    clean_year = normalize_text(year)
    clean_month = normalize_text(month)
    clean_day = normalize_text(day)
    clean_medline = normalize_text(medline_date)

    # 1. MedlineDate takes precedence if standard Year is missing
    if not clean_year and clean_medline:
        # Match 4-digit year at start of MedlineDate
        m_year = re.search(r"\b(19\d\d|20\d\d)\b", clean_medline)
        if m_year:
            clean_year = m_year.group(1)
            # Check for month in MedlineDate
            for m_name, m_num in MONTH_NAME_TO_NUM.items():
                if re.search(r"\b" + m_name + r"\b", clean_medline.lower()):
                    clean_month = m_num
                    break

    if not clean_year or not re.match(r"^\d{4}$", clean_year):
        raise ValueError(f"Unparseable publication year from date parts: year='{year}', medline='{medline_date}'")

    # 2. Check for season strings in month
    if clean_month and clean_month.lower() in SEASONS:
        # Season dates are strictly preserved at year precision
        return (clean_year, "year")

    # 3. Standardize month
    parsed_month: Optional[str] = None
    if clean_month:
        m_lower = clean_month.lower()
        if m_lower in MONTH_NAME_TO_NUM:
            parsed_month = MONTH_NAME_TO_NUM[m_lower]
        elif re.match(r"^\d{1,2}$", clean_month):
            parsed_month = f"{int(clean_month):02d}"
            if int(parsed_month) < 1 or int(parsed_month) > 12:
                parsed_month = None

    if not parsed_month:
        return (clean_year, "year")

    # 4. Standardize day
    parsed_day: Optional[str] = None
    if clean_day and re.match(r"^\d{1,2}$", clean_day):
        d_int = int(clean_day)
        if 1 <= d_int <= 31:
            parsed_day = f"{d_int:02d}"

    if parsed_day:
        return (f"{clean_year}-{parsed_month}-{parsed_day}", "day")
    else:
        return (f"{clean_year}-{parsed_month}", "month")


def split_list_field(raw_field: Optional[str]) -> List[Dict[str, Any]]:
    """
    Parse a comma-delimited list field using quote-aware CSV parsing with skipinitialspace=True.
    Returns list of dicts: {'text': str, 'is_artifact': bool, 'is_split_ambiguous': bool}
    """
    if not raw_field:
        return []

    cleaned = raw_field.strip()
    if not cleaned:
        return []

    raw_unbalanced_quotes = (cleaned.count('"') % 2 != 0)
    try:
        reader = csv.reader(io.StringIO(cleaned), delimiter=",", skipinitialspace=True, strict=True)
        tokens = next(reader, [])
    except Exception:
        # Delimiter corruption or unbalanced quotes
        return [{"text": cleaned, "is_artifact": True, "is_split_ambiguous": True}]

    results: List[Dict[str, Any]] = []
    for tok in tokens:
        t_str = tok.strip()
        if not t_str:
            continue

        is_artifact = False
        is_split_ambiguous = False

        # Check for malformed artifact conditions
        if raw_unbalanced_quotes or t_str.count('"') % 2 != 0:
            is_artifact = True
            is_split_ambiguous = True
        if t_str.endswith(",") or t_str.startswith(","):
            is_artifact = True
        if t_str.count("(") != t_str.count(")"):
            is_artifact = True
            is_split_ambiguous = True
        if t_str in ('()', '""', "''"):
            is_artifact = True

        results.append({
            "text": t_str,
            "is_artifact": is_artifact,
            "is_split_ambiguous": is_split_ambiguous
        })

    return results

