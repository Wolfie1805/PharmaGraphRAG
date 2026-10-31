"""
Investigate Item 2:
- PA164743704 raw value and item-by-item parse
- Unbalanced quote and unbalanced parenthesis check across all list-valued columns in all ClinPGx TSVs
"""

import zipfile
import csv
import io
import sys
from pathlib import Path

csv.field_size_limit(250000)
sys.stdout.reconfigure(encoding="utf-8")

raw_dir = Path("data/raw/clinpgx/20261030_79ff97e7")
haplo_dir = Path("data/raw/clinpgx/20261031_d2a604a2")

from app.normalization.normalize import split_list_field

# 1. PA164743704 in chemicals.tsv / drugs.tsv
print("=== 1. PA164743704 RAW VALUES AND PARSE ===")
for zname, fname in [("chemicals.zip", "chemicals.tsv"), ("drugs.zip", "drugs.tsv")]:
    with zipfile.ZipFile(raw_dir / zname) as z:
        lines = z.read(fname).decode("utf-8").splitlines()
        reader = csv.DictReader(lines, delimiter="\t")
        for r in reader:
            if r.get("PharmGKB Accession Id") == "PA164743704":
                raw_trade = r.get("Trade Names", "")
                print(f"File: {fname}")
                print(f"Raw Trade Names repr: {repr(raw_trade)}")
                print(f"Raw Trade Names str:  {raw_trade}")
                items = split_list_field(raw_trade)
                print(f"Parsed items count: {len(items)}")
                for i, it in enumerate(items, 1):
                    print(f"   [{i}] text={repr(it['text'])}, is_artifact={it['is_artifact']}, is_split_ambiguous={it['is_split_ambiguous']}")
                break

# 2. Check every list-valued column in every ClinPGx TSV
print("\n=== 2. UNBALANCED QUOTES AND PARENTHESES ACROSS ALL CLINPGX TSVS ===")
all_zips = list(raw_dir.glob("*.zip")) + list(haplo_dir.glob("*.zip"))

for zp in all_zips:
    with zipfile.ZipFile(zp) as z:
        for fn in z.namelist():
            if not fn.endswith(".tsv"):
                continue
            content = z.read(fn).decode("utf-8")
            reader = csv.DictReader(io.StringIO(content), delimiter="\t")
            fieldnames = reader.fieldnames or []
            
            # Find candidate list columns (or check all string columns)
            # We track per column: total rows, rows with unbalanced quotes, rows with unbalanced parens
            col_stats = {col: {"unbalanced_quotes": 0, "unbalanced_parens": 0, "examples": []} for col in fieldnames}
            
            total_rows = 0
            for row_idx, r in enumerate(reader, start=1):
                total_rows += 1
                for col in fieldnames:
                    val = r.get(col, "")
                    if not val:
                        continue
                    
                    unbal_q = (val.count('"') % 2 != 0)
                    unbal_p = (val.count('(') != val.count(')'))
                    
                    if unbal_q:
                        col_stats[col]["unbalanced_quotes"] += 1
                        if len(col_stats[col]["examples"]) < 2:
                            col_stats[col]["examples"].append((row_idx, "quote", val[:60]))
                    if unbal_p:
                        col_stats[col]["unbalanced_parens"] += 1
                        if len(col_stats[col]["examples"]) < 2:
                            col_stats[col]["examples"].append((row_idx, "paren", val[:60]))
            
            # Print columns that have any unbalanced items
            has_any = any(s["unbalanced_quotes"] > 0 or s["unbalanced_parens"] > 0 for s in col_stats.values())
            print(f"\n{zp.name} -> {fn} (total rows: {total_rows}):")
            if not has_any:
                print("   All columns: 0 unbalanced quotes, 0 unbalanced parentheses.")
            else:
                for col, s in col_stats.items():
                    if s["unbalanced_quotes"] > 0 or s["unbalanced_parens"] > 0:
                        print(f"   Column '{col}': {s['unbalanced_quotes']} unbalanced quotes, {s['unbalanced_parens']} unbalanced parentheses")
                        for ex in s["examples"]:
                            print(f"      Example row {ex[0]} ({ex[1]}): {repr(ex[2])}")
