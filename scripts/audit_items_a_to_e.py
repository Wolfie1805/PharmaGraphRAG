"""
Comprehensive audit script for Items A to E:
A. License audit of all 14 ClinPGx archives
B. Count reconciliation, breakdown by gene, and the 4 focus genes
C. SNV exact matches deep dive (1,694 matches, collisions, prefixes, 10 samples)
D. Cross-entity collisions (26 entries, short alias statistics)
E. Antithymocyte globulin raw inspection and full list-column unbalanced check
"""

import csv
import io
import json
import random
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(2147483647)

CLINPGX_RAW_DIR_1 = Path("data/raw/clinpgx/20261030_79ff97e7")
CLINPGX_RAW_DIR_2 = Path("data/raw/clinpgx/20261031_d2a604a2")

print("=== ITEM A.1: LICENSE / README AUDIT ACROSS ALL 14 ARCHIVES ===")
# Manifest 1: 11 files (10 zip + 1 json catalog)
# Manifest 2: 3 files (1 zip + 1 json catalog + 1 json cpic alleles)
all_archives = sorted(list(CLINPGX_RAW_DIR_1.glob("*")) + list(CLINPGX_RAW_DIR_2.glob("*")))

license_audit_results = {}
for path in all_archives:
    name = f"{path.parent.name}/{path.name}"
    if path.suffix == ".zip":
        with zipfile.ZipFile(path, "r") as z:
            namelist = z.namelist()
            license_files = [n for n in namelist if "license" in n.lower() or "readme" in n.lower()]
            if license_files:
                sentences = []
                for lf in license_files:
                    try:
                        content = z.read(lf).decode("utf-8", errors="replace")
                        first_line = [ln.strip() for ln in content.splitlines() if ln.strip()][:3]
                        sentences.append(f"{lf}: {' '.join(first_line)}")
                    except Exception as e:
                        sentences.append(f"{lf}: (binary/unreadable: {e})")
                license_audit_results[name] = "; ".join(sentences)
            else:
                license_audit_results[name] = "none included"
    elif path.suffix == ".json":
        license_audit_results[name] = "none included (JSON catalog/stream artifact)"
    else:
        license_audit_results[name] = "none included"

for k, v in license_audit_results.items():
    print(f"  {k} -> {v}")


print("\n=== ITEM B.1: HAPLOTYPE RECONCILIATION & RESOLVED/DANGLING METHOD ===")
# Compare why Haplotype was 728 / 286 before and 694 / 320 now
# Let's inspect the exact join sets
haplo_zip = CLINPGX_RAW_DIR_2 / "clinpgxHaplotypes.zip"
named_alleles_accs = set()
star_alleles_accs = set()
with zipfile.ZipFile(haplo_zip) as z:
    for r in csv.DictReader(
        io.StringIO(z.read("clinpgxHaplotypes_named_alleles.tsv").decode("utf-8")),
        delimiter="\t",
    ):
        named_alleles_accs.add(r["Accession ID"].strip())
    for r in csv.DictReader(
        io.StringIO(z.read("clinpgxHaplotypes_star_alleles.tsv").decode("utf-8")),
        delimiter="\t",
    ):
        star_alleles_accs.add(r["Accession ID"].strip())

cpic_json = CLINPGX_RAW_DIR_2 / "cpic.alleles.json"
cpic_allele_accs = set()
with open(cpic_json, "r", encoding="utf-8") as f:
    cpic_data = json.load(f)
    for it in cpic_data:
        acc = it.get("allele", {}).get("accessionId", "").strip()
        if acc:
            cpic_allele_accs.add(acc)

rel_zip = CLINPGX_RAW_DIR_1 / "relationships.zip"
with zipfile.ZipFile(rel_zip) as z:
    r_rows = list(
        csv.DictReader(io.StringIO(z.read("relationships.tsv").decode("utf-8")), delimiter="\t")
    )

haplo_endpoints = []
star_endpoints = []
hla_endpoints = []
for r in r_rows:
    for p in ["Entity1", "Entity2"]:
        t = r[f"{p}_type"].strip()
        i = r[f"{p}_id"].strip()
        if t == "Haplotype":
            haplo_endpoints.append(i)
        elif t == "StarAllele":
            star_endpoints.append(i)
        elif t == "HlaAllele":
            hla_endpoints.append(i)

print(f"Total Haplotype endpoint occurrences: {len(haplo_endpoints)}")
in_named = sum(1 for i in haplo_endpoints if i in named_alleles_accs)
in_cpic = sum(1 for i in haplo_endpoints if i in cpic_allele_accs)
in_both = sum(1 for i in haplo_endpoints if i in named_alleles_accs and i in cpic_allele_accs)
in_either_named_cpic = sum(
    1 for i in haplo_endpoints if (i in named_alleles_accs or i in cpic_allele_accs)
)
in_star = sum(1 for i in haplo_endpoints if i in star_alleles_accs)
in_all_three = sum(
    1
    for i in haplo_endpoints
    if (i in named_alleles_accs or i in cpic_allele_accs or i in star_alleles_accs)
)

print(f"  In named_alleles: {in_named}")
print(f"  In cpic_alleles: {in_cpic}")
print(f"  In both named and cpic: {in_both}")
print(
    f"  In either named or cpic: {in_either_named_cpic} "
    f"(dangling = {len(haplo_endpoints) - in_either_named_cpic})"
)
print(f"  In star_alleles: {in_star}")
print(
    f"  In named OR cpic OR star: {in_all_three} "
    f"(dangling = {len(haplo_endpoints) - in_all_three})"
)
# Notice: 694 + 34 = 728! Exactly 34 Haplotype endpoints in relationships.tsv
# have IDs defined in clinpgxHaplotypes_star_alleles.tsv!


print("\n=== ITEM B.2: BREAKDOWN OF UNRESOLVED ENDPOINTS BY GENE ===")
# Collect relationship endpoint IDs and their names for StarAllele, HlaAllele, Haplotype
unresolved_star_by_gene = Counter()
unresolved_hla_by_gene = Counter()
unresolved_haplo_by_gene = Counter()

# In relationships.tsv, Entity_name often contains the gene or allele symbol
# (e.g., "CYP2D6*4", "HLA-B*57:01")
for r in r_rows:
    for p in ["Entity1", "Entity2"]:
        t = r[f"{p}_type"].strip()
        i = r[f"{p}_id"].strip()
        n = r[f"{p}_name"].strip()

        # Check StarAllele
        if t == "StarAllele" and (i not in star_alleles_accs and i not in cpic_allele_accs):
            # Extract gene prefix
            g = n.split("*")[0].strip() if "*" in n else n.split()[0].strip()
            unresolved_star_by_gene[g] += 1

        # Check HlaAllele
        if t == "HlaAllele" and (i not in cpic_allele_accs):
            g = n.split("*")[0].strip() if "*" in n else n.split()[0].strip()
            unresolved_hla_by_gene[g] += 1

        # Check Haplotype
        if t == "Haplotype" and (
            i not in named_alleles_accs and i not in cpic_allele_accs and i not in star_alleles_accs
        ):
            g = n.split("*")[0].strip() if "*" in n else n.split()[0].strip()
            unresolved_haplo_by_gene[g] += 1

print(f"Unresolved StarAllele top 10 genes: {unresolved_star_by_gene.most_common(10)}")
print(f"Unresolved HlaAllele top 10 genes: {unresolved_hla_by_gene.most_common(10)}")
print(f"Unresolved Haplotype top 10 genes: {unresolved_haplo_by_gene.most_common(10)}")


print("\n=== ITEM B.3: FOUR FOCUS GENES (CYP2C19, CYP2C9, VKORC1, SLCO1B1) ===")
# For each gene:
# 1. How many allele entities defined in clinpgxHaplotypes star alleles
# 2. How many allele entities defined in clinpgxHaplotypes named alleles
# 3. How many allele entities defined in cpic.alleles.json
# 4. How many relationship endpoints remain unresolved
focus_genes = ["CYP2C19", "CYP2C9", "VKORC1", "SLCO1B1"]

star_by_gene = Counter()
with zipfile.ZipFile(haplo_zip) as z:
    for r in csv.DictReader(
        io.StringIO(z.read("clinpgxHaplotypes_star_alleles.tsv").decode("utf-8")),
        delimiter="\t",
    ):
        star_by_gene[r["Gene"].strip()] += 1

named_by_gene = Counter()
with zipfile.ZipFile(haplo_zip) as z:
    for r in csv.DictReader(
        io.StringIO(z.read("clinpgxHaplotypes_named_alleles.tsv").decode("utf-8")),
        delimiter="\t",
    ):
        named_by_gene[r["Gene"].strip()] += 1

cpic_by_gene = Counter()
for it in cpic_data:
    sym = it.get("allele", {}).get("gene", {}).get("symbol", "").strip()
    if sym:
        cpic_by_gene[sym] += 1

for g in focus_genes:
    # Check unresolved relationship endpoints for this gene
    unres_endpoints = 0
    total_endpoints = 0
    for r in r_rows:
        for p in ["Entity1", "Entity2"]:
            t = r[f"{p}_type"].strip()
            i = r[f"{p}_id"].strip()
            n = r[f"{p}_name"].strip()
            if t in ("StarAllele", "Haplotype", "HlaAllele"):
                gene_prefix = n.split("*")[0].strip() if "*" in n else n.split()[0].strip()
                if gene_prefix == g:
                    total_endpoints += 1
                    is_res = (
                        i in star_alleles_accs or i in named_alleles_accs or i in cpic_allele_accs
                    )
                    if not is_res:
                        unres_endpoints += 1

    print(f"Gene {g}:")
    print(f"  Star alleles in clinpgxHaplotypes: {star_by_gene[g]}")
    print(f"  Named alleles in clinpgxHaplotypes: {named_by_gene[g]}")
    print(f"  Alleles in cpic.alleles.json: {cpic_by_gene[g]}")
    print(f"  Relationship endpoints: total={total_endpoints}, unresolved={unres_endpoints}")
    print(
        f"  VKORC1 present? star={g in star_by_gene}, named={g in named_by_gene}, "
        f"cpic={g in cpic_by_gene}"
    )


print("\n=== ITEM C: SNV EXACT MATCHES DEEP DIVE ===")
# Re-read variants.tsv
variants_zip = CLINPGX_RAW_DIR_1 / "variants.zip"
with zipfile.ZipFile(variants_zip) as z:
    var_rows = list(
        csv.DictReader(io.StringIO(z.read("variants.tsv").decode("utf-8")), delimiter="\t")
    )

# Map each synonym token to list of variants
syn_to_variants = defaultdict(list)
for v in var_rows:
    syns = v.get("Synonyms", "").strip()
    if syns:
        try:
            tokens = list(csv.reader(io.StringIO(syns), skipinitialspace=True))[0]
            for tok in tokens:
                tok_clean = tok.strip()
                if tok_clean:
                    syn_to_variants[tok_clean].append(v)
        except Exception:
            pass

# Find SNV names from relationships.tsv
snv_endpoints = defaultdict(list)
for r in r_rows:
    for p in ["Entity1", "Entity2"]:
        if r[f"{p}_type"] == "SNV":
            snv_endpoints[r[f"{p}_name"].strip()].append(r[f"{p}_id"].strip())

print(f"Total unique SNV names: {len(snv_endpoints)}")
matched_snvs = {k: syn_to_variants[k] for k in snv_endpoints if k in syn_to_variants}
print(f"Matched SNV strings: {len(matched_snvs)}")

# 1. How many SNV strings match >1 rsID variant?
snv_matching_mult_variants = {
    k: v for k, v in matched_snvs.items() if len(set(x["Variant ID"] for x in v)) > 1
}
print(f"SNV strings matching >1 rsID variant: {len(snv_matching_mult_variants)}")

# 2. How many variants are matched by >1 SNV string?
var_to_matched_snvs = defaultdict(set)
for k, v_list in matched_snvs.items():
    for v in v_list:
        var_to_matched_snvs[v["Variant ID"]].add(k)
variants_matched_by_mult_snvs = {k: v for k, v in var_to_matched_snvs.items() if len(v) > 1}
print(f"Variants matched by >1 SNV string: {len(variants_matched_by_mult_snvs)}")

# 3. Counts by reference sequence accession and version prefix (e.g. NC_0000xx.yy)
prefix_counts = Counter()
for k in matched_snvs:
    m = re.match(r'^(NC_\d+\.\d+)', k)
    if m:
        prefix_counts[m.group(1)] += 1
    else:
        # non-NC prefix
        prefix_counts[k.split(":")[0]] += 1

print(f"Top 10 RefSeq prefix counts: {prefix_counts.most_common(10)}")

# 4. 10 deterministic seeded sample matches
random.seed(42)
sample_keys = sorted(list(matched_snvs.keys()))
sampled_snvs = random.sample(sample_keys, 10)

samples_data = []
for k in sampled_snvs:
    matching_var = matched_snvs[k][0]
    samples_data.append({
        "snv_name": k,
        "snv_ids": list(set(snv_endpoints[k])),
        "matched_variant_id": matching_var["Variant ID"],
        "matched_variant_name": matching_var["Variant Name"],
        "gene_symbols": matching_var["Gene Symbols"],
        "location": matching_var["Location"]
    })

print("\n10 Seeded Sample Matches:")
for s in samples_data:
    print(
        f"  SNV '{s['snv_name']}' (IDs: {s['snv_ids'][:2]}) -> Variant "
        f"{s['matched_variant_id']} ({s['matched_variant_name']}) in {s['gene_symbols']} "
        f"at {s['location']}"
    )

# Write snv_variant_exact_matches.jsonl
review_dir = Path("data/review")
review_dir.mkdir(parents=True, exist_ok=True)
snv_matches_path = review_dir / "snv_variant_exact_matches.jsonl"
with open(snv_matches_path, "w", encoding="utf-8") as f:
    for k in sorted(list(matched_snvs.keys())):
        for v in matched_snvs[k]:
            rec = {
                "snv_name": k,
                "snv_ids": list(set(snv_endpoints[k])),
                "matched_variant_id": v["Variant ID"],
                "matched_variant_name": v["Variant Name"],
                "gene_symbols": v["Gene Symbols"],
                "location": v["Location"]
            }
            f.write(json.dumps(rec) + "\n")
print(f"Written all {len(matched_snvs)} matches to {snv_matches_path}")


print("\n=== ITEM D: CROSS-ENTITY COLLISIONS & SHORT ALIASES ===")
# Build the 26 collisions and write to data/review/cross_entity_collisions.jsonl
# Load genes
genes_zip = CLINPGX_RAW_DIR_1 / "genes.zip"
gene_map = defaultdict(set)
with zipfile.ZipFile(genes_zip) as z:
    for r in csv.DictReader(io.StringIO(z.read("genes.tsv").decode("utf-8")), delimiter="\t"):
        gid = r["PharmGKB Accession Id"]
        sym = r["Symbol"].strip()
        name = r["Name"].strip()
        if sym:
            gene_map[sym.lower()].add((gid, sym, "symbol"))
        if name:
            gene_map[name.lower()].add((gid, name, "name"))

# Load chemicals & synonyms
chems_zip = CLINPGX_RAW_DIR_1 / "chemicals.zip"
chem_map = defaultdict(set)
all_short_aliases = Counter()
short_alias_collisions = []

with zipfile.ZipFile(chems_zip) as z:
    for r in csv.DictReader(io.StringIO(z.read("chemicals.tsv").decode("utf-8")), delimiter="\t"):
        cid = r["PharmGKB Accession Id"]
        cname = r["Name"].strip()
        if cname:
            chem_map[cname.lower()].add((cid, cname, "name"))

        # Synonyms and Trade names
        for field in ["Alternate Names", "Trade Names"]:
            val = r.get(field, "").strip()
            if val:
                try:
                    for tok in list(csv.reader(io.StringIO(val), skipinitialspace=True))[0]:
                        tok_s = tok.strip()
                        if tok_s:
                            chem_map[tok_s.lower()].add((cid, tok_s, field))
                            if len(tok_s) <= 3:
                                all_short_aliases[tok_s.lower()] += 1
                except Exception:
                    pass

# Intersect
cross_collisions_list = []
collisions_path = review_dir / "cross_entity_collisions.jsonl"
with open(collisions_path, "w", encoding="utf-8") as f:
    for k in sorted(list(set(gene_map.keys()) & set(chem_map.keys()))):
        genes = [{"accession": g[0], "matched_text": g[1], "field": g[2]} for g in gene_map[k]]
        chemicals = [{"accession": c[0], "matched_text": c[1], "field": c[2]} for c in chem_map[k]]
        rec = {
            "surface_form": k,
            "char_length": len(k),
            "genes": genes,
            "chemicals": chemicals
        }
        f.write(json.dumps(rec) + "\n")
        cross_collisions_list.append(rec)
        if len(k) <= 3:
            short_alias_collisions.append(k)

print(f"Written {len(cross_collisions_list)} cross-entity collisions to {collisions_path}")
print(f"Total chemical aliases with length <= 3 characters: {len(all_short_aliases)}")
print(
    f"Short chemical aliases (<= 3 chars) colliding with gene symbols: "
    f"{len(short_alias_collisions)}"
)
print("Short alias collision examples:", short_alias_collisions[:10])


print("\n=== ITEM E: ANTITHYMOCYTE GLOBULIN RAW INSPECTION & FULL LIST-COLUMN CHECK ===")
# 1. Exact raw field value for PA164743704
drugs_zip = CLINPGX_RAW_DIR_1 / "drugs.zip"
with zipfile.ZipFile(drugs_zip) as z:
    for r in csv.DictReader(io.StringIO(z.read("drugs.tsv").decode("utf-8")), delimiter="\t"):
        if r["PharmGKB Accession Id"] == "PA164743704":
            raw_tg = r.get("Trade Names", "")
            print("Antithymocyte globulin raw Trade Names:")
            print("  Raw string (repr):", repr(raw_tg))
            parsed_default = list(csv.reader(io.StringIO(raw_tg), skipinitialspace=True))[0]
            print("  Parsed items:")
            for idx, it in enumerate(parsed_default):
                print(f"    Item {idx+1}: {repr(it)}")

# 2. Check unbalanced quotes and parens across ALL list-valued columns in ALL files
list_columns_check = [
    (
        "genes.zip",
        "genes.tsv",
        ["Alternative Names", "Alternative Symbols", "Cross-references"],
    ),
    (
        "drugs.zip",
        "drugs.tsv",
        ["Trade Names", "Alternate Names", "Cross-references", "External Vocabulary"],
    ),
    (
        "chemicals.zip",
        "chemicals.tsv",
        ["Trade Names", "Alternate Names", "Cross-references", "External Vocabulary"],
    ),
    ("variants.zip", "variants.tsv", ["Gene IDs", "Gene Symbols", "Synonyms"]),
    ("clinicalVariants.zip", "clinicalVariants.tsv", ["chemicals", "phenotypes"]),
    ("drugLabels.zip", "drugLabels.tsv", ["Chemicals", "Genes", "Variants/Haplotypes"]),
    ("relationships.zip", "relationships.tsv", ["PMIDs"]),
    ("clinpgxHaplotypes.zip", "clinpgxHaplotypes_star_alleles.tsv", []),
    ("clinpgxHaplotypes.zip", "clinpgxHaplotypes_named_alleles.tsv", []),
]

malformed_artifacts = []
print("\nUnbalanced Check Across All List Columns:")
for zname, fname, cols in list_columns_check:
    target_dir = CLINPGX_RAW_DIR_2 if "Haplotypes" in zname else CLINPGX_RAW_DIR_1
    with zipfile.ZipFile(target_dir / zname) as z:
        reader = csv.DictReader(io.StringIO(z.read(fname).decode("utf-8")), delimiter="\t")
        for r_idx, r in enumerate(reader):
            for c in cols:
                val = r.get(c, "").strip()
                if not val:
                    continue
                # Check unbalanced quotes
                q_count = val.count('"')
                p_open = val.count('(')
                p_close = val.count(')')
                unb_quotes = (q_count % 2 != 0)
                unb_parens = (p_open != p_close)

                if unb_quotes or unb_parens:
                    item_id = (
                        r.get("PharmGKB Accession Id")
                        or r.get("Variant ID")
                        or r.get("Accession ID")
                        or f"row_{r_idx + 1}"
                    )
                    malformed_artifacts.append({
                        "file": fname,
                        "column": c,
                        "record_id": item_id,
                        "unbalanced_quotes": unb_quotes,
                        "unbalanced_parens": unb_parens,
                        "raw_value": val[:120]
                    })

print(f"Total malformed records found across all files: {len(malformed_artifacts)}")
artifacts_by_file_col = Counter((x["file"], x["column"]) for x in malformed_artifacts)
for fc, cnt in artifacts_by_file_col.items():
    print(f"  {fc[0]} -> {fc[1]}: {cnt} rows")

# Write to review file
artifacts_path = review_dir / "malformed_list_artifacts.jsonl"
with open(artifacts_path, "w", encoding="utf-8") as f:
    for a in malformed_artifacts:
        f.write(json.dumps(a) + "\n")
print(f"Written malformed list artifacts to {artifacts_path}")
