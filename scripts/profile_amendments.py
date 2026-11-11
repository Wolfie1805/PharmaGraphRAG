"""
Comprehensive profiling script for Phase 2 amendments:
1. PubMed full corpus (3,096 records across 16 XML files)
2. Haplotype files: clinpgxHaplotypes.zip, cpic.alleles.json
3. Field length character measurements & Brand Mixtures validation
4. Synonym collisions across drugs and chemicals
5. Relationships.tsv complete endpoint matrix & dangling analysis
6. Trade Names quote-aware comma splitting
"""

import csv
import io
import json
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

# Increase csv field limit safely for Windows 32-bit C long
csv.field_size_limit(2147483647)

CLINPGX_RAW_DIR = Path("data/raw/clinpgx/20261030_79ff97e7")
HAPLO_RAW_DIR = Path("data/raw/clinpgx/20261031_d2a604a2")
PUBMED_FULL_DIR = Path("data/raw/pubmed/20261031_7d1398e0")


def profile_pubmed_full():
    print("=== PUBMED FULL CORPUS PROFILING ===")
    xml_files = sorted(list(PUBMED_FULL_DIR.glob("*.xml")))
    print(f"Total XML files: {len(xml_files)}")

    total_articles = 0
    total_book_articles = 0
    pmids = set()
    abstract_sections = Counter()
    has_abstract = 0
    no_abstract = 0
    has_mesh = 0
    no_mesh = 0
    mesh_heading_counts = Counter()
    pub_years = Counter()
    journal_counts = Counter()

    for xf in xml_files:
        tree = ET.parse(xf)
        root = tree.getroot()
        for art in root.findall(".//PubmedArticle"):
            total_articles += 1
            pmid = art.findtext(".//MedlineCitation/PMID")
            if pmid:
                pmids.add(pmid.strip())

            # Abstract
            abstract_texts = art.findall(".//Abstract/AbstractText")
            if abstract_texts:
                has_abstract += 1
                for ab in abstract_texts:
                    lbl = ab.attrib.get("Label") or ab.attrib.get("NlmCategory") or "UNLABELED"
                    abstract_sections[lbl] += 1
            else:
                no_abstract += 1

            # MeSH
            mesh_list = art.findall(".//MeshHeadingList/MeshHeading")
            if mesh_list:
                has_mesh += 1
                for mh in mesh_list:
                    desc = mh.findtext("DescriptorName")
                    if desc:
                        mesh_heading_counts[desc.strip()] += 1
            else:
                no_mesh += 1

            # Pub Year
            year = (
                art.findtext(".//JournalIssue/PubDate/Year")
                or art.findtext(".//DateCompleted/Year")
                or "UNKNOWN"
            )
            pub_years[year] += 1

            # Journal
            jtitle = art.findtext(".//Journal/Title") or "UNKNOWN"
            journal_counts[jtitle] += 1

        for b_art in root.findall(".//PubmedBookArticle"):
            total_book_articles += 1
            pmid = b_art.findtext(".//BookDocument/PMID")
            if pmid:
                pmids.add(pmid.strip())
            abstract_texts = b_art.findall(".//Abstract/AbstractText")
            if abstract_texts:
                has_abstract += 1
            else:
                no_abstract += 1
            no_mesh += 1 # books don't have standard mesh headings list

    print(f"Total records: {total_articles + total_book_articles}")
    print(f"  PubmedArticle: {total_articles}")
    print(f"  PubmedBookArticle: {total_book_articles}")
    print(f"Unique PMIDs: {len(pmids)}")
    print(f"Abstract presence: {has_abstract} with abstract, {no_abstract} without")
    print(f"MeSH presence: {has_mesh} with MeSH, {no_mesh} without")
    print(f"Top 5 Abstract sections: {abstract_sections.most_common(5)}")
    print(f"Top 5 MeSH Descriptors: {mesh_heading_counts.most_common(5)}")
    valid_years = [k for k in pub_years if k.isdigit()]
    print(f"Pub Year range: min={min(valid_years)}, max={max(valid_years)}")
    return {
        "total_records": total_articles + total_book_articles,
        "articles": total_articles,
        "books": total_book_articles,
        "unique_pmids": len(pmids),
        "has_abstract": has_abstract,
        "no_abstract": no_abstract,
        "has_mesh": has_mesh,
        "no_mesh": no_mesh,
        "top_abstract_sections": abstract_sections.most_common(10),
        "top_mesh": mesh_heading_counts.most_common(10),
        "year_distribution": dict(pub_years.most_common(10))
    }


def profile_haplotypes():
    print("\n=== HAPLOTYPE / ALLELE FILES PROFILING ===")
    results = {}

    # 1. clinpgxHaplotypes.zip
    zip_path = HAPLO_RAW_DIR / "clinpgxHaplotypes.zip"
    with zipfile.ZipFile(zip_path, "r") as z:
        namelist = z.namelist()
        print(f"clinpgxHaplotypes.zip contents: {namelist}")
        target_name = [n for n in namelist if n.endswith(".tsv") or n.endswith(".txt")][0]
        content = z.read(target_name).decode("utf-8")
        reader = csv.DictReader(io.StringIO(content), delimiter="\t")
        rows = list(reader)
        print(f"clinpgxHaplotypes rows: {len(rows)}, columns: {reader.fieldnames}")

        # Check null rates
        cols = reader.fieldnames
        null_counts = Counter()
        for r in rows:
            for c in cols:
                if not r[c] or not r[c].strip():
                    null_counts[c] += 1

        sample_row = rows[0] if rows else {}
        null_rates_list = [
            (c, null_counts[c], round(null_counts[c] / len(rows) * 100, 2)) for c in cols
        ]
        print(f"Null rates: {null_rates_list}")
        print(f"Sample row: {sample_row}")

        results["clinpgxHaplotypes"] = {
            "file": target_name,
            "row_count": len(rows),
            "columns": cols,
            "null_rates": {
                c: {"nulls": null_counts[c], "pct": round(null_counts[c] / len(rows) * 100, 2)}
                for c in cols
            },
            "sample": sample_row,
        }

    # 2. cpic.alleles.json
    json_path = HAPLO_RAW_DIR / "cpic.alleles.json"
    with open(json_path, "r", encoding="utf-8") as f:
        cpic_data = json.load(f)

    print(f"cpic.alleles.json type: {type(cpic_data)}, length: {len(cpic_data)}")
    if isinstance(cpic_data, list):
        print(f"CPIC sample item keys: {list(cpic_data[0].keys())}")
        print(f"CPIC sample item: {cpic_data[0]}")
        genes = set(
            item.get("genesymbol") or item.get("geneSymbol") or item.get("gene")
            for item in cpic_data
        )
        sample_genes = sorted(list(str(g) for g in genes if g))[:5]
        print(f"Unique genes in CPIC alleles: {len(genes)}, e.g. {sample_genes}")

        # Check fields across all items
        key_counts = Counter()
        for item in cpic_data:
            for k in item.keys():
                key_counts[k] += 1
        print(f"Keys frequency: {key_counts}")
        results["cpic_alleles"] = {
            "record_count": len(cpic_data),
            "keys": list(key_counts.keys()),
            "unique_genes": len(genes),
            "sample": cpic_data[0]
        }
    return results


def profile_field_lengths_and_brand_mixtures():
    print("\n=== FIELD LENGTH IN CHARACTERS & BRAND MIXTURES ===")
    max_char_by_file = {}

    # Check all ClinPGx archives
    for zip_file in sorted(CLINPGX_RAW_DIR.glob("*.zip")):
        with zipfile.ZipFile(zip_file, "r") as z:
            for n in z.namelist():
                if not (n.endswith(".tsv") or n.endswith(".txt")):
                    continue
                content = z.read(n).decode("utf-8")
                reader = csv.reader(io.StringIO(content), delimiter="\t")
                header = next(reader, None)
                if not header:
                    continue
                max_len = 0
                max_col = ""
                max_row_idx = 0
                total_rows = 0
                col_count_mismatch = 0

                for row in reader:
                    total_rows += 1
                    if len(row) != len(header):
                        col_count_mismatch += 1
                    for idx, val in enumerate(row):
                        if len(val) > max_len:
                            max_len = len(val)
                            max_col = header[idx] if idx < len(header) else f"col_{idx}"
                            max_row_idx = total_rows

                max_char_by_file[f"{zip_file.name}:{n}"] = {
                    "total_rows": total_rows,
                    "max_char": max_len,
                    "max_col": max_col,
                    "max_row_idx": max_row_idx,
                    "col_count_mismatch": col_count_mismatch
                }
                print(
                    f"{zip_file.name} / {n}: {total_rows} rows, max_char={max_len} "
                    f"(in column '{max_col}' at row {max_row_idx}), mismatch={col_count_mismatch}"
                )

    # Specific inspection of drugs.tsv and chemicals.tsv Brand Mixtures
    drugs_zip = CLINPGX_RAW_DIR / "drugs.zip"
    with zipfile.ZipFile(drugs_zip, "r") as z:
        content = z.read("drugs.tsv").decode("utf-8")
        reader = csv.reader(io.StringIO(content), delimiter="\t")
        header = next(reader)
        print(f"\ndrugs.tsv header len: {len(header)}")
        for idx, row in enumerate(reader):
            for c_idx, val in enumerate(row):
                if len(val) > 100000:
                    print(
                        f"FOUND LONG FIELD in drugs.tsv row {idx + 1}: "
                        f"col '{header[c_idx]}', length={len(val)}"
                    )
                    print(f"Row column count: {len(row)} (expected {len(header)})")
                    print(f"Row ID: {row[0]}, Name: {row[1]}")
                    print(f"Field preview (first 150 chars): {val[:150]}")
                    print(f"Field preview (last 150 chars): {val[-150:]}")

    return max_char_by_file


def profile_synonym_collisions():
    print("\n=== DRUGS / CHEMICALS SYNONYM COLLISIONS ===")
    drugs_zip = CLINPGX_RAW_DIR / "drugs.zip"
    chems_zip = CLINPGX_RAW_DIR / "chemicals.zip"

    # Map accession to names, synonyms, trade names
    accession_to_data = {}

    for zpath, tname, is_drug_val in [
        (drugs_zip, "drugs.tsv", True),
        (chems_zip, "chemicals.tsv", False),
    ]:
        with zipfile.ZipFile(zpath, "r") as z:
            content = z.read(tname).decode("utf-8")
            reader = csv.DictReader(io.StringIO(content), delimiter="\t")
            for r in reader:
                acc = r["PharmGKB Accession Id"].strip()
                if acc not in accession_to_data:
                    accession_to_data[acc] = {
                        "name": r.get("Name", "").strip(),
                        "synonyms": set(),
                        "trade_names": set(),
                        "is_drug": is_drug_val
                    }
                else:
                    if is_drug_val:
                        accession_to_data[acc]["is_drug"] = True

                # Parse synonyms (quoted comma-separated)
                raw_syns = r.get("Alternate Names", "").strip()
                if raw_syns:
                    # Parse using csv reader on string
                    syn_reader = csv.reader(io.StringIO(raw_syns))
                    try:
                        syn_list = next(syn_reader)
                        for s in syn_list:
                            s_clean = s.strip()
                            if s_clean:
                                accession_to_data[acc]["synonyms"].add(s_clean)
                    except Exception:
                        pass

                raw_trade = r.get("Trade Names", "").strip()
                if raw_trade:
                    trade_reader = csv.reader(io.StringIO(raw_trade))
                    try:
                        t_list = next(trade_reader)
                        for t in t_list:
                            t_clean = t.strip()
                            if t_clean:
                                accession_to_data[acc]["trade_names"].add(t_clean)
                    except Exception:
                        pass

    print(f"Total unified chemical accessions: {len(accession_to_data)}")

    # Check synonym-level collisions
    # Case-folded string -> set of accessions
    syn_to_accs = defaultdict(set)
    trade_to_accs = defaultdict(set)
    all_surface_to_accs = defaultdict(set)

    for acc, data in accession_to_data.items():
        primary = data["name"].lower().strip()
        if primary:
            all_surface_to_accs[primary].add(acc)
        for s in data["synonyms"]:
            s_norm = s.lower().strip()
            if s_norm:
                syn_to_accs[s_norm].add(acc)
                all_surface_to_accs[s_norm].add(acc)
        for t in data["trade_names"]:
            t_norm = t.lower().strip()
            if t_norm:
                trade_to_accs[t_norm].add(acc)
                all_surface_to_accs[t_norm].add(acc)

    colliding_syns = {k: v for k, v in syn_to_accs.items() if len(v) > 1}
    colliding_trades = {k: v for k, v in trade_to_accs.items() if len(v) > 1}
    colliding_all = {k: v for k, v in all_surface_to_accs.items() if len(v) > 1}

    print(f"Synonym-only collisions (case-folded): {len(colliding_syns)}")
    print(f"Trade-name-only collisions (case-folded): {len(colliding_trades)}")
    print(f"All surface forms collisions (name + syn + trade): {len(colliding_all)}")

    # Show top examples
    examples = []
    for k in sorted(colliding_all.keys(), key=lambda x: len(colliding_all[x]), reverse=True)[:10]:
        accs = colliding_all[k]
        names = [f"{a} ({accession_to_data[a]['name']})" for a in accs]
        examples.append((k, len(accs), names))
        print(f"  Collision '{k}' -> {len(accs)} entities: {names[:3]}")

    return {
        "total_accessions": len(accession_to_data),
        "colliding_syns_count": len(colliding_syns),
        "colliding_trades_count": len(colliding_trades),
        "colliding_all_count": len(colliding_all),
        "top_examples": examples
    }


def profile_relationships():
    print("\n=== RELATIONSHIPS.TSV COMPLETE ENDPOINT MATRIX ===")
    rel_zip = CLINPGX_RAW_DIR / "relationships.zip"

    # Collect all known IDs from other files
    known_genes = set()
    with zipfile.ZipFile(CLINPGX_RAW_DIR / "genes.zip", "r") as z:
        for r in csv.DictReader(io.StringIO(z.read("genes.tsv").decode("utf-8")), delimiter="\t"):
            known_genes.add(r["PharmGKB Accession Id"].strip())

    known_chems = set()
    with zipfile.ZipFile(CLINPGX_RAW_DIR / "chemicals.zip", "r") as z:
        chems_reader = csv.DictReader(
            io.StringIO(z.read("chemicals.tsv").decode("utf-8")), delimiter="\t"
        )
        for r in chems_reader:
            known_chems.add(r["PharmGKB Accession Id"].strip())
    with zipfile.ZipFile(CLINPGX_RAW_DIR / "drugs.zip", "r") as z:
        for r in csv.DictReader(io.StringIO(z.read("drugs.tsv").decode("utf-8")), delimiter="\t"):
            known_chems.add(r["PharmGKB Accession Id"].strip())

    known_variants = set()
    with zipfile.ZipFile(CLINPGX_RAW_DIR / "variants.zip", "r") as z:
        vars_reader = csv.DictReader(
            io.StringIO(z.read("variants.tsv").decode("utf-8")), delimiter="\t"
        )
        for r in vars_reader:
            known_variants.add(r["Variant ID"].strip())

    known_haplotypes = set()
    with zipfile.ZipFile(HAPLO_RAW_DIR / "clinpgxHaplotypes.zip", "r") as z:
        target = [n for n in z.namelist() if n.endswith(".tsv") or n.endswith(".txt")][0]
        for r in csv.DictReader(io.StringIO(z.read(target).decode("utf-8")), delimiter="\t"):
            hap_id = (
                r.get("Haplotype ID", "").strip()
                or r.get("PharmGKB Accession Id", "").strip()
            )
            known_haplotypes.add(hap_id)

    # Read relationships.tsv
    with zipfile.ZipFile(rel_zip, "r") as z:
        content = z.read("relationships.tsv").decode("utf-8")
        reader = csv.DictReader(io.StringIO(content), delimiter="\t")
        total_rows = 0
        endpoint_types = Counter()
        pair_types = Counter()
        dangling_by_type = Counter()
        total_dangling = 0

        for r in reader:
            total_rows += 1
            t1 = r["Entity1_type"].strip()
            id1 = r["Entity1_id"].strip()
            t2 = r["Entity2_type"].strip()
            id2 = r["Entity2_id"].strip()

            endpoint_types[t1] += 1
            endpoint_types[t2] += 1
            pair_types[f"{t1} -- {t2}"] += 1

            # Check dangling
            known_other_types = (
                "Gene",
                "Chemical",
                "Drug",
                "Variant",
                "VariantLocation",
                "Haplotype",
            )
            dang1 = False
            dang2 = False

            if t1 == "Gene" and id1 not in known_genes:
                dang1 = True
            elif t1 in ("Chemical", "Drug") and id1 not in known_chems:
                dang1 = True
            elif t1 in ("Variant", "VariantLocation") and id1 not in known_variants:
                dang1 = True
            elif t1 == "Haplotype" and id1 not in known_haplotypes:
                dang1 = True
            elif t1 not in known_other_types:
                dang1 = True

            if t2 == "Gene" and id2 not in known_genes:
                dang2 = True
            elif t2 in ("Chemical", "Drug") and id2 not in known_chems:
                dang2 = True
            elif t2 in ("Variant", "VariantLocation") and id2 not in known_variants:
                dang2 = True
            elif t2 == "Haplotype" and id2 not in known_haplotypes:
                dang2 = True
            elif t2 not in known_other_types:
                dang2 = True

            if dang1:
                dangling_by_type[t1] += 1
            if dang2:
                dangling_by_type[t2] += 1
            if dang1 or dang2:
                total_dangling += 1

    print(f"Total relationships rows: {total_rows}")
    print(f"Endpoint types: {endpoint_types}")
    print(f"Top 10 Pair types: {pair_types.most_common(10)}")
    print(f"Dangling by endpoint type: {dangling_by_type}")
    print(f"Total dangling rows: {total_dangling} ({round(total_dangling/total_rows*100, 2)}%)")

    return {
        "total_rows": total_rows,
        "endpoint_types": dict(endpoint_types),
        "pair_types": dict(pair_types),
        "dangling_by_type": dict(dangling_by_type),
        "total_dangling": total_dangling
    }


def main():
    profile_pubmed = profile_pubmed_full()
    haplo = profile_haplotypes()
    lengths = profile_field_lengths_and_brand_mixtures()
    syns = profile_synonym_collisions()
    rels = profile_relationships()

    out_path = Path("scripts/profiling_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "pubmed": profile_pubmed,
            "haplotypes": haplo,
            "field_lengths": lengths,
            "synonyms": syns,
            "relationships": rels
        }, f, indent=2)
    print(f"\nAll profiling results written to {out_path}")

if __name__ == "__main__":
    main()

