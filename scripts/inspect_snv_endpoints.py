import zipfile
import csv
import io

CLINPGX_RAW_DIR = "data/raw/clinpgx/20261030_79ff97e7"
z_rel = zipfile.ZipFile(f"{CLINPGX_RAW_DIR}/relationships.zip")
reader = csv.DictReader(io.StringIO(z_rel.read("relationships.tsv").decode("utf-8")), delimiter="\t")

print("=== SAMPLE SNV ENDPOINTS IN RELATIONSHIPS.TSV ===")
count = 0
for r in reader:
    for p in ["Entity1", "Entity2"]:
        if r[f"{p}_type"] == "SNV":
            print(f"ID: {r[f'{p}_id']} | Name: {r[f'{p}_name']} | Other: {r['Entity1_name' if p=='Entity2' else 'Entity2_name']} ({r['Entity1_type' if p=='Entity2' else 'Entity2_type']}) | Assoc: {r['Association']}")
            count += 1
            break
    if count >= 10:
        break
