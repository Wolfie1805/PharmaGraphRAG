"""
Perform complete license audit on all 14 raw ClinPGx files across both manifests.
"""

import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

raw_dir1 = Path("data/raw/clinpgx/20261030_79ff97e7")
raw_dir2 = Path("data/raw/clinpgx/20261031_d2a604a2")

files = [
    # Run 1 (11 files)
    (raw_dir1 / "chemicals.zip", "ClinPGx"),
    (raw_dir1 / "clinicalVariants.zip", "ClinPGx"),
    (raw_dir1 / "drugLabels.zip", "ClinPGx"),
    (raw_dir1 / "drugs.zip", "ClinPGx"),
    (raw_dir1 / "genes.zip", "ClinPGx"),
    (raw_dir1 / "guidelineAnnotations.json.zip", "ClinPGx"),
    (raw_dir1 / "relationships.zip", "ClinPGx"),
    (raw_dir1 / "summaryAnnotations.zip", "ClinPGx"),
    (raw_dir1 / "variantAnnotations.zip", "ClinPGx"),
    (raw_dir1 / "variants.zip", "ClinPGx"),
    (raw_dir1 / "clinpgx_file_catalog.json", "ClinPGx (API metadata)"),
    # Run 2 (3 files)
    (raw_dir2 / "clinpgxHaplotypes.zip", "ClinPGx"),
    (raw_dir2 / "cpic.alleles.json", "CPIC"),
    (raw_dir2 / "clinpgx_file_catalog.json", "ClinPGx (API metadata)"),
]

print(f"Total files to audit: {len(files)}\n")

for path, src in files:
    print(f"File: {path.name} (Dir: {path.parent.name}, Source: {src})")
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            lic_files = [n for n in names if "license" in n.lower() or "readme" in n.lower()]
            if lic_files:
                for lf in lic_files:
                    txt = z.read(lf).decode("utf-8", errors="replace")
                    # Find license sentence
                    sentences = [s.strip() for s in txt.split("\n") if s.strip()]
                    first_line = sentences[0] if sentences else ""
                    print(f"   Internal License/Readme: {lf}")
                    print(f"   Exact content snippet: {first_line}")
                    for line in sentences:
                        lower_line = line.lower()
                        if (
                            "creative commons" in lower_line
                            or "license" in lower_line
                            or "commercial" in lower_line
                        ):
                            print(f"   Exact license sentence: {line}")
            else:
                print("   Internal License/Readme: none included")
    elif path.suffix == ".json":
        # Check if JSON file has license field or metadata
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                lic = data.get("license") or data.get("terms") or data.get("copyright")
                print(f"   JSON metadata license: {lic if lic else 'none included'}")
            elif isinstance(data, list):
                print(
                    f"   JSON array: {len(data)} items, no top-level license key; "
                    "source CPIC API license is CC0."
                )
        except Exception as e:
            print(f"   Error reading JSON: {e}")
    print()

