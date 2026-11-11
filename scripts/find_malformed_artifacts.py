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

    for r in reader:
        raw = r.get("Trade Names", "").strip()
        if not raw:
            continue
        acc = r["PharmGKB Accession Id"]
        name = r["Name"]

        try:
            items = list(csv.reader(io.StringIO(raw)))[0]
            for it in items:
                it_clean = it.strip()
                # Check for malformed source artifacts:
                # - starts with comma or quote
                # - ends with quote or unmatched paren
                # - empty string or pure punctuation
                # - leading/trailing invalid chars
                is_artifact = False
                reason = []
                if it_clean.startswith(","):
                    is_artifact = True
                    reason.append("leading_comma")
                if it_clean.endswith('"') and not it_clean.startswith('"'):
                    is_artifact = True
                    reason.append("trailing_unmatched_quote")
                if it_clean.startswith('"') and not it_clean.endswith('"'):
                    is_artifact = True
                    reason.append("leading_unmatched_quote")
                if it_clean in ('()', '""', ''):
                    is_artifact = True
                    reason.append("empty_or_brackets_only")
                if it_clean.count("(") != it_clean.count(")"):
                    is_artifact = True
                    reason.append("unbalanced_parens")

                if is_artifact:
                    flagged_artifacts.append((acc, name, it_clean, "|".join(reason)))
        except Exception:
            pass

    print(f"=== {filename} FLAGGED MALFORMED TRADE NAME ARTIFACTS ===")
    print(f"Total flagged artifacts: {len(flagged_artifacts)}")
    for f in flagged_artifacts:
        print(f"  {f[0]} ({f[1]}): {repr(f[2])} -> {f[3]}")
