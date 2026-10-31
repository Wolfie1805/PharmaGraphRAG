import zipfile
import csv
import io

csv.field_size_limit(250000)
z = zipfile.ZipFile("data/raw/clinpgx/20261030_79ff97e7/drugs.zip")
reader = csv.DictReader(io.StringIO(z.read("drugs.tsv").decode("utf-8")), delimiter="\t")

print("=== ALL ROWS WITH PARENS AND COMMAS IN TRADE NAMES ===")
for r in reader:
    t = r.get("Trade Names", "").strip()
    if "(" in t and "," in t:
        print(f"\n{r['PharmGKB Accession Id']} ({r['Name']}):")
        print(f"  Raw: {t}")
        # Show how csv.reader splits it vs parenthetical commas
        parsed = list(csv.reader(io.StringIO(t)))[0]
        # Check if any paren has a comma inside it
        for idx, item in enumerate(parsed):
            if "(" in item or ")" in item:
                print(f"    Item {idx}: {repr(item)}")
