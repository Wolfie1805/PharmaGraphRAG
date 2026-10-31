"""
Benchmark and run Stage A with detailed progress logging.
"""

import sys
import time
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

from app.normalization.pipeline import run_normalization_pipeline

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

dir_run1 = Path("data/processed/run1")
dir_run2 = Path("data/processed/run2")

print("Starting Run 1...", flush=True)
t0 = time.time()
res1 = run_normalization_pipeline(dir_run1)
t1 = time.time()
print(f"Run 1 completed in {t1 - t0:.2f}s", flush=True)

print("Starting Run 2...", flush=True)
t2 = time.time()
res2 = run_normalization_pipeline(dir_run2)
t3 = time.time()
print(f"Run 2 completed in {t3 - t2:.2f}s", flush=True)

print("Verifying hash matches...", flush=True)
all_match = True
for f in res1["parquet_hashes"]:
    h1 = res1["parquet_hashes"][f]
    h2 = res2["parquet_hashes"][f]
    m = (h1 == h2)
    if not m:
        all_match = False
    print(f"  {f}: match={m} (Run 1: {h1[:16]}, Run 2: {h2[:16]})", flush=True)

if not all_match:
    print("Determinism check FAILED!")
    sys.exit(1)

print("100% Determinism check PASSED!", flush=True)

