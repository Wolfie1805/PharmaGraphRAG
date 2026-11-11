"""
Runner for Stage A:
Executes the normalization pipeline twice into two separate directories
and proves 100% byte-identical outputs.
"""

import json
import shutil
import sys
from pathlib import Path

from app.normalization.pipeline import run_normalization_pipeline

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

DIR_RUN1 = Path("data/processed/run1")
DIR_RUN2 = Path("data/processed/run2")
FINAL_DIR = Path("data/processed")

if DIR_RUN1.exists():
    shutil.rmtree(DIR_RUN1)
if DIR_RUN2.exists():
    shutil.rmtree(DIR_RUN2)

print("=== EXECUTING NORMALIZATION PIPELINE RUN 1 ===")
res1 = run_normalization_pipeline(DIR_RUN1)
print("Run 1 Parquet SHA-256 hashes:")
for f, h in res1["parquet_hashes"].items():
    print(f"  {f}: {h}")

print("\n=== EXECUTING NORMALIZATION PIPELINE RUN 2 (DETERMINISM CHECK) ===")
res2 = run_normalization_pipeline(DIR_RUN2)
print("Run 2 Parquet SHA-256 hashes:")
for f, h in res2["parquet_hashes"].items():
    print(f"  {f}: {h}")

print("\n=== COMPARING RUN 1 VS RUN 2 FOR EXACT BYTE IDENTICALITY ===")
all_match = True
for f in res1["parquet_hashes"]:
    h1 = res1["parquet_hashes"][f]
    h2 = res2["parquet_hashes"][f]
    match = (h1 == h2)
    if not match:
        all_match = False
    print(f"  {f}: match={match} (Run1: {h1[:16]}..., Run2: {h2[:16]}...)")

if all_match:
    print("\nSUCCESS: 100% BYTE-FOR-BYTE REPRODUCIBLE DETERMINISM PROVED!")
    # Copy files from Run 1 to FINAL_DIR
    for p in DIR_RUN1.glob("*"):
        shutil.copy2(p, FINAL_DIR / p.name)
    shutil.rmtree(DIR_RUN1)
    shutil.rmtree(DIR_RUN2)
    print(f"Moved verified Parquet tables and reject logs to {FINAL_DIR}")
else:
    print("\nERROR: DETERMINISM CHECK FAILED!")
    sys.exit(1)

# Dump run summary
summary_path = Path("scripts/stage_a_summary.json")
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump({
        "accounting": res1["accounting"],
        "table_counts": res1["table_counts"],
        "parquet_hashes": res1["parquet_hashes"]
    }, f, indent=2)
print(f"Summary written to {summary_path}")

