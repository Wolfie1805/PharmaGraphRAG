"""Measure all exact facts required for Phase 2 Task 1 review."""

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(2147483647)

CLINPGX_DIR = Path("data/raw/clinpgx/20261030_79ff97e7")
PUBMED_DIR = Path("data/raw/pubmed")


def measure_all():
    results = {}

    # =========================================================================
    # A. PUBMED STATUS
    # =========================================================================
    pubmed_dirs = [d.name for d in PUBMED_DIR.iterdir() if d.is_dir()]
    manifest_path = Path("data/manifests/manifest_pubmed_20261030_9a48695d.json")
    pubmed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    results["pubmed_status"] = {
        "directories": pubmed_dirs,
        "is_pilot": pubmed_manifest.get("is_pilot"),
        "pilot_selection_rule": pubmed_manifest.get("pilot_selection_rule"),
        "queries": pubmed_manifest.get("queries"),
        "esearch_counts": pubmed_manifest.get("esearch_counts"),
        "pmids_retrieved_count": len(pubmed_manifest.get("pmids_retrieved", [])),
        "reconciliation": pubmed_manifest.get("reconciliation"),
        "pmid_to_queries": pubmed_manifest.get("pmid_to_queries"),
    }

    # =========================================================================
    # B.1 DRUGS vs CHEMICALS OVERLAP
    # =========================================================================
    with zipfile.ZipFile(CLINPGX_DIR / "drugs.zip") as z:
        with z.open("drugs.tsv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t")
            drugs_data = {row["PharmGKB Accession Id"]: row["Name"] for row in reader}

    with zipfile.ZipFile(CLINPGX_DIR / "chemicals.zip") as z:
        with z.open("chemicals.tsv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t")
            chem_data = {row["PharmGKB Accession Id"]: row["Name"] for row in reader}

    drug_ids = set(drugs_data.keys())
    chem_ids = set(chem_data.keys())
    in_both = drug_ids & chem_ids
    only_drugs = drug_ids - chem_ids
    only_chem = chem_ids - drug_ids

    # Same name under different accessions
    name_to_ids = defaultdict(set)
    for aid, name in {**drugs_data, **chem_data}.items():
        name_to_ids[name.strip().lower()].add(aid)
    same_name_diff_id = {name: list(ids) for name, ids in name_to_ids.items() if len(ids) > 1}

    results["drugs_vs_chemicals"] = {
        "drugs_count": len(drug_ids),
        "chemicals_count": len(chem_ids),
        "in_both_count": len(in_both),
        "only_drugs_count": len(only_drugs),
        "only_chemicals_count": len(only_chem),
        "duplicate_names_count": len(same_name_diff_id),
        "sample_duplicate_names": list(same_name_diff_id.items())[:5],
    }

    # =========================================================================
    # B.3 MAXIMUM FIELD LENGTH PER FILE
    # =========================================================================
    max_field_lengths = {}
    for zip_file in sorted(CLINPGX_DIR.glob("*.zip")):
        if zip_file.name == "guidelineAnnotations.json.zip":
            continue
        with zipfile.ZipFile(zip_file) as z:
            for tsv_name in z.namelist():
                if not tsv_name.endswith(".tsv"):
                    continue
                with z.open(tsv_name) as f:
                    wrapper = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
                    reader = csv.reader(wrapper, delimiter="\t")
                    max_len = 0
                    max_col = ""
                    header = next(reader)
                    for row in reader:
                        for col_idx, cell in enumerate(row):
                            if len(cell) > max_len:
                                max_len = len(cell)
                                max_col = header[col_idx] if col_idx < len(header) else f"col_{col_idx}"
                    max_field_lengths[f"{zip_file.name}#{tsv_name}"] = {
                        "max_length_bytes": max_len,
                        "column": max_col,
                    }

    results["max_field_lengths"] = max_field_lengths

    # =========================================================================
    # B.4 STAR ALLELES & HAPLOTYPES IN SELECTED FILES & CATALOG
    # =========================================================================
    # Catalog check
    catalog_json = json.loads((CLINPGX_DIR / "clinpgx_file_catalog.json").read_text(encoding="utf-8"))
    catalog_files = [x["fileName"] for x in catalog_json.get("data", [])]
    haplotype_files_in_catalog = [f for f in catalog_files if "haplotype" in f.lower() or "allele" in f.lower()]

    # Variants file inspection for star alleles
    star_allele_pat = re.compile(r"\*[0-9]+[A-Za-z]*")
    variants_with_star = 0
    variants_with_rsid = 0
    star_with_gene_count = 0
    bare_star_count = 0

    with zipfile.ZipFile(CLINPGX_DIR / "variants.zip") as z:
        with z.open("variants.tsv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t")
            for row in reader:
                vname = row.get("Variant Name", "")
                if star_allele_pat.search(vname):
                    variants_with_star += 1
                    if row.get("Gene Symbols") or row.get("Gene IDs"):
                        star_with_gene_count += 1
                    else:
                        bare_star_count += 1
                if vname.lower().startswith("rs"):
                    variants_with_rsid += 1

    # Check relationships.tsv for star allele to rsid links
    star_to_rsid_links = 0
    rel_entity_types = Counter()
    with zipfile.ZipFile(CLINPGX_DIR / "relationships.zip") as z:
        with z.open("relationships.tsv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t")
            for row in reader:
                t1 = row.get("Entity1_type", "")
                t2 = row.get("Entity2_type", "")
                rel_entity_types[f"{t1} -> {t2}"] += 1
                n1 = row.get("Entity1_name", "")
                n2 = row.get("Entity2_name", "")
                if (star_allele_pat.search(n1) and n2.lower().startswith("rs")) or (
                    star_allele_pat.search(n2) and n1.lower().startswith("rs")
                ):
                    star_to_rsid_links += 1

    results["star_alleles_and_haplotypes"] = {
        "catalog_haplotype_files": haplotype_files_in_catalog,
        "variants_with_star_alleles": variants_with_star,
        "variants_with_rsid": variants_with_rsid,
        "star_with_gene_context": star_with_gene_count,
        "bare_star_alleles": bare_star_count,
        "star_to_rsid_links_in_relationships": star_to_rsid_links,
    }

    # =========================================================================
    # B.5 MULTI-VALUE FIELD SEPARATORS & AMBIGUOUS COMMAS
    # =========================================================================
    # Test Trade Names in drugs.tsv
    trade_names_with_internal_commas = []
    with zipfile.ZipFile(CLINPGX_DIR / "drugs.zip") as z:
        with z.open("drugs.tsv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t")
            for row in reader:
                tn = row.get("Trade Names", "")
                if '"' in tn or " (" in tn and "," in tn:
                    trade_names_with_internal_commas.append(tn)

    results["trade_names_ambiguity"] = {
        "sample_trade_names_with_commas_or_quotes": trade_names_with_internal_commas[:10],
        "count_potentially_ambiguous": len(trade_names_with_internal_commas),
    }

    # =========================================================================
    # B.6 RELATIONSHIPS.TSV ENDPOINT TYPES & DANGLING CHECK
    # =========================================================================
    # Load all primary IDs from genes, drugs, chemicals, variants
    with zipfile.ZipFile(CLINPGX_DIR / "genes.zip") as z:
        with z.open("genes.tsv") as f:
            gene_ids = {row["PharmGKB Accession Id"] for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t")}

    with zipfile.ZipFile(CLINPGX_DIR / "variants.zip") as z:
        with z.open("variants.tsv") as f:
            variant_ids = {row["Variant ID"] for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t")}

    all_registered_ids = gene_ids | drug_ids | chem_ids | variant_ids

    total_rel_rows = 0
    dangling_endpoint1 = 0
    dangling_endpoint2 = 0
    dangling_both = 0
    rel_types = Counter()

    with zipfile.ZipFile(CLINPGX_DIR / "relationships.zip") as z:
        with z.open("relationships.tsv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t")
            rel_cols = reader.fieldnames
            for row in reader:
                total_rel_rows += 1
                e1 = row.get("Entity1_id", "")
                e2 = row.get("Entity2_id", "")
                t1 = row.get("Entity1_type", "")
                t2 = row.get("Entity2_type", "")
                rel = row.get("Association", "")
                rel_types[rel] += 1

                e1_missing = e1 not in all_registered_ids
                e2_missing = e2 not in all_registered_ids

                if e1_missing and e2_missing:
                    dangling_both += 1
                elif e1_missing:
                    dangling_endpoint1 += 1
                elif e2_missing:
                    dangling_endpoint2 += 1

    results["relationships_profile"] = {
        "columns": rel_cols,
        "total_rows": total_rel_rows,
        "top_endpoint_type_pairs": dict(rel_entity_types.most_common(10)),
        "association_types": dict(rel_types.most_common(10)),
        "dangling_endpoint1_only": dangling_endpoint1,
        "dangling_endpoint2_only": dangling_endpoint2,
        "dangling_both_endpoints": dangling_both,
        "total_dangling_rows": dangling_endpoint1 + dangling_endpoint2 + dangling_both,
    }

    out_file = Path("docs/phase2/phase2_measured_facts.json")
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results written to {out_file}")


if __name__ == "__main__":
    measure_all()
