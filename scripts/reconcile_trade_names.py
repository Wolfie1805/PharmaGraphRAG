import zipfile
import csv
import io
import re

CLINPGX_RAW_DIR = "data/raw/clinpgx/20261030_79ff97e7"
csv.field_size_limit(2147483647)

z = zipfile.ZipFile(f"{CLINPGX_RAW_DIR}/drugs.zip")
reader = csv.DictReader(io.StringIO(z.read("drugs.tsv").decode("utf-8")), delimiter="\t")

rows_with_comma_and_quote_or_paren = 0
examples = []

for r in reader:
    t = r.get("Trade Names", "").strip()
    if not t:
        continue
    # Check if row has comma AND (quote or paren)
    if (('"' in t) or ('(' in t)) and (',' in t):
        rows_with_comma_and_quote_or_paren += 1
        examples.append((r["PharmGKB Accession Id"], r["Name"], t))

print(f"Total rows with comma AND (quote or paren): {rows_with_comma_and_quote_or_paren}")
print("Samples:")
for acc, name, t in examples[:10]:
    has_q = '"' in t
    has_p = '(' in t
    print(f"  {acc} ({name}): quotes={has_q}, parens={has_p} -> {repr(t[:100])}")
