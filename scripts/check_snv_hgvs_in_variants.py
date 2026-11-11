import csv
import io
import zipfile

CLINPGX_RAW_DIR = "data/raw/clinpgx/20261030_79ff97e7"
csv.field_size_limit(250000)

# 1. Collect all SNV endpoint names and IDs from relationships.tsv
z_rel = zipfile.ZipFile(f"{CLINPGX_RAW_DIR}/relationships.zip")
reader_rel = csv.DictReader(
    io.StringIO(z_rel.read("relationships.tsv").decode("utf-8")), delimiter="\t"
)

snv_names = set()
snv_ids = set()
snv_id_to_name = {}

for r in reader_rel:
    for p in ["Entity1", "Entity2"]:
        if r[f"{p}_type"] == "SNV":
            i = r[f"{p}_id"].strip()
            n = r[f"{p}_name"].strip()
            snv_ids.add(i)
            snv_names.add(n)
            snv_id_to_name[i] = n

print(f"Total unique SNV IDs: {len(snv_ids)}")
print(f"Total unique SNV Names (HGVS/coords): {len(snv_names)}")

# 2. Inspect variants.tsv columns
z_var = zipfile.ZipFile(f"{CLINPGX_RAW_DIR}/variants.zip")
reader_var = csv.DictReader(
    io.StringIO(z_var.read("variants.tsv").decode("utf-8")), delimiter="\t"
)
var_rows = list(reader_var)

# Check exact matches against each column in variants.tsv
print("\n--- Testing exact matches in variants.tsv ---")
for col in reader_var.fieldnames:
    # Check against SNV ID
    matched_ids = sum(1 for r in var_rows if r[col].strip() in snv_ids)
    # Check against SNV Name
    matched_names = sum(1 for r in var_rows if r[col].strip() in snv_names)
    print(f"Col '{col}': matched_ids={matched_ids}, matched_names={matched_names}")

# In variants.tsv, Synonyms is a comma-separated list. Let's parse Synonyms!
synonym_tokens = set()
for r in var_rows:
    syns = r.get("Synonyms", "").strip()
    if syns:
        try:
            tokens = list(csv.reader(io.StringIO(syns), skipinitialspace=True))[0]
            for tok in tokens:
                synonym_tokens.add(tok.strip())
        except Exception:
            pass

print(f"\nTotal individual synonym tokens in variants.tsv: {len(synonym_tokens)}")
matched_snv_names_in_var_syns = snv_names & synonym_tokens
print(
    "Exact SNV Names matching an individual token in variants.tsv 'Synonyms': "
    f"{len(matched_snv_names_in_var_syns)}"
)
if matched_snv_names_in_var_syns:
    print(
        "Sample matched SNV names in variants.tsv Synonyms:",
        list(matched_snv_names_in_var_syns)[:5],
    )

# Also check without the '=' reference allele notation
# (e.g. g.104941653G= vs g.104941653G>A or coords)
snv_names_stripped_eq = set()
for n in snv_names:
    if n.endswith("="):
        snv_names_stripped_eq.add(n[:-1])
matched_stripped = snv_names_stripped_eq & synonym_tokens
print(
    "SNV names stripped of trailing '=' matching variants.tsv Synonyms: "
    f"{len(matched_stripped)}"
)

# Also check clinpgxHaplotypes HGVS column
z_haplo = zipfile.ZipFile("data/raw/clinpgx/20261031_d2a604a2/clinpgxHaplotypes.zip")
for hfile in ["clinpgxHaplotypes_star_alleles.tsv", "clinpgxHaplotypes_named_alleles.tsv"]:
    hreader = csv.DictReader(io.StringIO(z_haplo.read(hfile).decode("utf-8")), delimiter="\t")
    hrows = list(hreader)
    hgvs_vals = set(r["HGVS"].strip() for r in hrows if r["HGVS"].strip())
    m = snv_names & hgvs_vals
    print(f"SNV Names matching {hfile} HGVS: {len(m)}")
