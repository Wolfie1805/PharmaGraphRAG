import json
import zipfile
import csv
import io
import re
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(2147483647)

CLINPGX_RAW_DIR = Path("data/raw/clinpgx/20261030_79ff97e7")
HAPLO_RAW_DIR = Path("data/raw/clinpgx/20261031_d2a604a2")

print("=== 1. CPIC.ALLELES.JSON GENE RECOUNT ===")
with open(HAPLO_RAW_DIR / "cpic.alleles.json", "r", encoding="utf-8") as f:
    cpic_data = json.load(f)

genes_in_cpic = set()
for item in cpic_data:
    symbol = item.get("allele", {}).get("gene", {}).get("symbol")
    if symbol:
        genes_in_cpic.add(symbol)

sorted_genes = sorted(list(genes_in_cpic))
print(f"Total unique gene symbols in cpic.alleles.json: {len(sorted_genes)}")
print("List of genes:", sorted_genes)


print("\n=== 2. JOIN KEYS & EXACT ID-ONLY RESOLUTION COUNTS ===")
# Load authoritative IDs
genes_zip = CLINPGX_RAW_DIR / "genes.zip"
known_gene_ids = set()
with zipfile.ZipFile(genes_zip) as z:
    for r in csv.DictReader(io.StringIO(z.read("genes.tsv").decode("utf-8")), delimiter="\t"):
        known_gene_ids.add(r["PharmGKB Accession Id"].strip())

chems_zip = CLINPGX_RAW_DIR / "chemicals.zip"
known_chem_ids = set()
with zipfile.ZipFile(chems_zip) as z:
    for r in csv.DictReader(io.StringIO(z.read("chemicals.tsv").decode("utf-8")), delimiter="\t"):
        known_chem_ids.add(r["PharmGKB Accession Id"].strip())

variants_zip = CLINPGX_RAW_DIR / "variants.zip"
known_var_ids = set()
with zipfile.ZipFile(variants_zip) as z:
    for r in csv.DictReader(io.StringIO(z.read("variants.tsv").decode("utf-8")), delimiter="\t"):
        known_var_ids.add(r["Variant ID"].strip())

haplo_zip = HAPLO_RAW_DIR / "clinpgxHaplotypes.zip"
known_star_ids = set()
known_named_ids = set()
with zipfile.ZipFile(haplo_zip) as z:
    for r in csv.DictReader(io.StringIO(z.read("clinpgxHaplotypes_star_alleles.tsv").decode("utf-8")), delimiter="\t"):
        known_star_ids.add(r["Accession ID"].strip())
    for r in csv.DictReader(io.StringIO(z.read("clinpgxHaplotypes_named_alleles.tsv").decode("utf-8")), delimiter="\t"):
        known_named_ids.add(r["Accession ID"].strip())

known_cpic_ids = set(item["allele"]["accessionId"].strip() for item in cpic_data if "allele" in item and "accessionId" in item["allele"])

# Now evaluate relationships.tsv by ID join only
rel_zip = CLINPGX_RAW_DIR / "relationships.zip"
with zipfile.ZipFile(rel_zip) as z:
    reader = csv.DictReader(io.StringIO(z.read("relationships.tsv").decode("utf-8")), delimiter="\t")
    
    total_endpoints_by_type = Counter()
    resolved_by_id = Counter()
    dangling_by_id = Counter()
    
    for r in reader:
        for prefix in ["Entity1", "Entity2"]:
            t = r[f"{prefix}_type"].strip()
            i = r[f"{prefix}_id"].strip()
            total_endpoints_by_type[t] += 1
            
            is_res = False
            if t == "Gene" and i in known_gene_ids: is_res = True
            elif t == "Chemical" and i in known_chem_ids: is_res = True
            elif t == "Variant" and i in known_var_ids: is_res = True
            elif t == "StarAllele" and (i in known_star_ids or i in known_cpic_ids): is_res = True
            elif t == "HlaAllele" and i in known_cpic_ids: is_res = True
            elif t == "Haplotype" and (i in known_named_ids or i in known_cpic_ids): is_res = True
            # SNV, Phenotype, GeneCopyNumberVariation have no dedicated definition file
            
            if is_res:
                resolved_by_id[t] += 1
            else:
                dangling_by_id[t] += 1

print("Endpoint Type | Total Occurrences | Join Key | Resolved (ID-only) | Dangling (ID-only)")
for t in ["Chemical", "SNV", "Phenotype", "Variant", "Gene", "StarAllele", "HlaAllele", "Haplotype", "GeneCopyNumberVariation"]:
    tot = total_endpoints_by_type[t]
    res = resolved_by_id[t]
    dang = dangling_by_id[t]
    key_desc = "PharmGKB Accession Id" if t in ("Chemical", "Gene", "StarAllele", "HlaAllele", "Haplotype") else ("Variant ID (PA...)" if t == "Variant" else "None (No primary file)")
    print(f"{t:20} | {tot:10} | {key_desc:25} | {res:10} | {dang:10}")


print("\n=== 3. TRADE NAMES & PARENTHETICAL COMMAS ===")
# Inspect chemicals.tsv and drugs.tsv for quotes, parens, and commas
for filename, zpath in [("drugs.tsv", CLINPGX_RAW_DIR / "drugs.zip"), ("chemicals.tsv", CLINPGX_RAW_DIR / "chemicals.zip")]:
    z = zipfile.ZipFile(zpath)
    content = z.read(filename).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    
    total_trades = 0
    rows_with_quotes = 0
    rows_with_parens = 0
    rows_with_commas_in_parens = 0
    rows_with_commas_in_quotes = 0
    malformed_source_artifacts = []
    
    for r in reader:
        raw = r.get("Trade Names", "").strip()
        if not raw:
            continue
        total_trades += 1
        acc = r["PharmGKB Accession Id"]
        name = r["Name"]
        
        if '"' in raw:
            rows_with_quotes += 1
        if '(' in raw and ')' in raw:
            rows_with_parens += 1
            
        # Check commas inside parens
        # regex for parens
        parens_matches = re.findall(r'\([^)]*\)', raw)
        has_comma_in_paren = any(',' in p for p in parens_matches)
        if has_comma_in_paren:
            rows_with_commas_in_parens += 1
            
        # Check quoted items via csv.reader
        try:
            items = list(csv.reader(io.StringIO(raw)))[0]
            for it in items:
                it_str = it.strip()
                # Check for malformed source artifacts like leading/trailing comma, unmatched quotes
                if it_str.startswith(",") or it_str.endswith('"') or it_str.startswith('"') or not re.match(r'^[A-Za-z0-9]', it_str):
                    malformed_source_artifacts.append((acc, name, it_str))
        except Exception as e:
            pass
            
    print(f"--- {filename} ---")
    print(f"Total rows with Trade Names: {total_trades}")
    print(f"Rows with quotes: {rows_with_quotes}")
    print(f"Rows with parentheses: {rows_with_parens}")
    print(f"Rows with commas inside parentheses: {rows_with_commas_in_parens}")
    print(f"Malformed source artifacts count: {len(malformed_source_artifacts)}")
    for art in malformed_source_artifacts[:5]:
        print(f"  Artifact in {art[0]} ({art[1]}): {repr(art[2])}")


print("\n=== 5. CROSS-ENTITY SURFACE FORM COLLISIONS ===")
# Check collisions across Gene, Chemical, Variant
# Load gene symbols and names
gene_surfaces = defaultdict(set)
with zipfile.ZipFile(genes_zip) as z:
    for r in csv.DictReader(io.StringIO(z.read("genes.tsv").decode("utf-8")), delimiter="\t"):
        gid = r["PharmGKB Accession Id"]
        sym = r["Symbol"].strip()
        name = r["Name"].strip()
        if sym: gene_surfaces[sym.lower()].add(("Gene", gid, sym))
        if name: gene_surfaces[name.lower()].add(("Gene", gid, name))

chem_surfaces = defaultdict(set)
with zipfile.ZipFile(chems_zip) as z:
    for r in csv.DictReader(io.StringIO(z.read("chemicals.tsv").decode("utf-8")), delimiter="\t"):
        cid = r["PharmGKB Accession Id"]
        name = r["Name"].strip()
        if name: chem_surfaces[name.lower()].add(("Chemical", cid, name))
        # Synonyms
        syns = r.get("Alternate Names", "")
        if syns:
            try:
                for s in list(csv.reader(io.StringIO(syns)))[0]:
                    s = s.strip()
                    if s: chem_surfaces[s.lower()].add(("Chemical", cid, s))
            except Exception: pass
        trades = r.get("Trade Names", "")
        if trades:
            try:
                for t in list(csv.reader(io.StringIO(trades)))[0]:
                    t = t.strip()
                    if t: chem_surfaces[t.lower()].add(("Chemical", cid, t))
            except Exception: pass

cross_collisions = defaultdict(list)
for k in set(gene_surfaces.keys()) & set(chem_surfaces.keys()):
    cross_collisions[k].extend(list(gene_surfaces[k]))
    cross_collisions[k].extend(list(chem_surfaces[k]))

print(f"Cross-entity collisions (Gene vs Chemical): {len(cross_collisions)}")
print("Sample cross-entity collisions:")
for k in sorted(list(cross_collisions.keys()))[:10]:
    types = [x[0] for x in cross_collisions[k]]
    details = [f"{x[0]}:{x[1]}({x[2]})" for x in cross_collisions[k]]
    print(f"  '{k}' -> {details}")


print("\n=== B.2 SNV ENDPOINTS VS VARIANTS.TSV HGVS/COORDINATES ===")
# Check if variants.tsv or other files have columns with HGVS strings matching SNV endpoint IDs
with zipfile.ZipFile(variants_zip) as z:
    var_content = z.read("variants.tsv").decode("utf-8")
    var_reader = csv.DictReader(io.StringIO(var_content), delimiter="\t")
    var_cols = var_reader.fieldnames
    print("variants.tsv columns:", var_cols)
    var_rows = list(var_reader)

# Sample SNV endpoint IDs from relationships.tsv
snv_ids = set()
with zipfile.ZipFile(rel_zip) as z:
    for r in csv.DictReader(io.StringIO(z.read("relationships.tsv").decode("utf-8")), delimiter="\t"):
        for p in ["Entity1", "Entity2"]:
            if r[f"{p}_type"] == "SNV":
                snv_ids.add(r[f"{p}_id"].strip())

print(f"Total unique SNV endpoint IDs in relationships.tsv: {len(snv_ids)}")
print("Sample SNV IDs:", list(snv_ids)[:5])

# Check each column in variants.tsv for exact match against SNV IDs
for col in var_cols:
    matches = sum(1 for r in var_rows if r[col].strip() in snv_ids)
    if matches > 0:
        print(f"Column '{col}' matched {matches} SNV IDs!")
    else:
        # Check partial/substring
        pass

# Check other files: clinicalVariants.tsv, var_drug_ann.tsv, clinpgxHaplotypes
clin_var_zip = CLINPGX_RAW_DIR / "clinicalVariants.zip"
with zipfile.ZipFile(clin_var_zip) as z:
    cv_reader = csv.DictReader(io.StringIO(z.read("clinicalVariants.tsv").decode("utf-8")), delimiter="\t")
    print("clinicalVariants.tsv columns:", cv_reader.fieldnames)
    for col in cv_reader.fieldnames:
        m = sum(1 for r in cv_reader if r[col].strip() in snv_ids)
        if m > 0: print(f"clinicalVariants.tsv '{col}' matched {m} SNV IDs!")

# Also check if SNV name (Entity_name) is HGVS or ID
with zipfile.ZipFile(rel_zip) as z:
    for r in csv.DictReader(io.StringIO(z.read("relationships.tsv").decode("utf-8")), delimiter="\t"):
        if r["Entity1_type"] == "SNV":
            print("SNV ID:", r["Entity1_id"], "| SNV Name:", r["Entity1_name"])
            break
