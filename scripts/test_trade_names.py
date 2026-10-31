import zipfile
import csv
import io

drugs_zip = "data/raw/clinpgx/20261030_79ff97e7/drugs.zip"
chems_zip = "data/raw/clinpgx/20261030_79ff97e7/chemicals.zip"

csv.field_size_limit(2147483647)

for name, p in [("drugs.tsv", drugs_zip), ("chemicals.tsv", chems_zip)]:
    z = zipfile.ZipFile(p)
    reader = csv.DictReader(io.StringIO(z.read(name).decode("utf-8")), delimiter="\t")
    total_with_trades = 0
    total_parsed_names = 0
    unbalanced_quotes = 0
    has_quotes = 0
    has_commas = 0
    comma_inside_quoted_name = 0
    
    for r in reader:
        trades = r.get("Trade Names", "").strip()
        if not trades:
            continue
        total_with_trades += 1
        if '"' in trades:
            has_quotes += 1
        if ',' in trades:
            has_commas += 1
        
        try:
            parsed = list(csv.reader(io.StringIO(trades)))[0]
            total_parsed_names += len(parsed)
            for item in parsed:
                if ',' in item:
                    comma_inside_quoted_name += 1
        except Exception as e:
            unbalanced_quotes += 1
            print(f"Unbalanced quote in {r['PharmGKB Accession Id']}: {trades}")
            
    print(f"=== {name} ===")
    print(f"Total records with trade names: {total_with_trades}")
    print(f"Records with quotes: {has_quotes}")
    print(f"Records with commas: {has_commas}")
    print(f"Unbalanced quote errors: {unbalanced_quotes}")
    print(f"Total individual trade names extracted: {total_parsed_names}")
    print(f"Trade names containing literal commas (inside quotes): {comma_inside_quoted_name}")

print("\n--- Detailed Quoted Names with Commas ---")
z = zipfile.ZipFile(drugs_zip)
for r in csv.DictReader(io.StringIO(z.read("drugs.tsv").decode("utf-8")), delimiter="\t"):
    trades = r.get("Trade Names", "").strip()
    if trades and '"' in trades:
        parsed = list(csv.reader(io.StringIO(trades)))[0]
        for item in parsed:
            if ',' in item:
                print(f"{r['PharmGKB Accession Id']} ({r['Name']}): {repr(item)}")
