import csv
import io
import zipfile

csv.field_size_limit(250000)

for filename, path in [
    ("drugs.tsv", "data/raw/clinpgx/20261030_79ff97e7/drugs.zip"),
    ("chemicals.tsv", "data/raw/clinpgx/20261030_79ff97e7/chemicals.zip"),
]:
    z = zipfile.ZipFile(path)
    reader = csv.DictReader(io.StringIO(z.read(filename).decode("utf-8")), delimiter="\t")

    flagged_artifacts = []
    total_parsed_names = 0

    for r in reader:
        raw = r.get("Trade Names", "").strip()
        if not raw:
            continue
        acc = r["PharmGKB Accession Id"]
        name = r["Name"]

        try:
            # Using skipinitialspace=True
            items = list(csv.reader(io.StringIO(raw), skipinitialspace=True))[0]
            total_parsed_names += len(items)
            for it in items:
                it_clean = it.strip()
                is_artifact = False
                reasons = []
                if it_clean.endswith(",") or it_clean.startswith(","):
                    is_artifact = True
                    reasons.append("dangling_comma")
                if it_clean in ('()', '""', ''):
                    is_artifact = True
                    reasons.append("empty_or_brackets_only")
                if it_clean.count("(") != it_clean.count(")"):
                    is_artifact = True
                    reasons.append("unbalanced_parens")
                if '"' in it_clean:
                    is_artifact = True
                    reasons.append("contains_quote")

                if is_artifact:
                    flagged_artifacts.append((acc, name, it_clean, "|".join(reasons)))
        except Exception:
            pass

    print(f"=== {filename} WITH skipinitialspace=True ===")
    print(f"Total individual trade names: {total_parsed_names}")
    print(f"Total flagged artifacts: {len(flagged_artifacts)}")
    for f in flagged_artifacts:
        print(f"  {f[0]} ({f[1]}): {repr(f[2])} -> {f[3]}")
