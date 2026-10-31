"""
Compute exact Item 3 endpoint recount:
- Resolved vs dangling per endpoint type
- Before/after for Haplotype (728 vs 694 vs star alleles)
- Table of dangling rows by combination of endpoint types (Entity1_type + Entity2_type)
- Final total dangling rows
"""

import sys
from pathlib import Path
from collections import Counter, defaultdict

from app.normalization.parsers.clinpgx import ClinPGxParser
from app.normalization.parsers.cpic import CPICParser

sys.stdout.reconfigure(encoding="utf-8")

raw_dir = Path("data/raw/clinpgx/20261030_79ff97e7")
haplo_dir = Path("data/raw/clinpgx/20261031_d2a604a2")

clinpgx_parser = ClinPGxParser(raw_dir, haplo_dir, "20261030_79ff97e7", "20261031_d2a604a2")
cpic_parser = CPICParser(haplo_dir / "cpic.alleles.json", "20261031_d2a604a2")

genes, _, _ = clinpgx_parser.parse_genes()
chems, _, _ = clinpgx_parser.parse_chemicals_and_drugs()
vars_, _ = clinpgx_parser.parse_variants()
haplos = clinpgx_parser.parse_haplotypes()
cpic = cpic_parser.parse_alleles()

primary_entities = genes + chems + vars_ + haplos + cpic

# Canonical mapping
known_ids = {}
for e in primary_entities:
    known_ids[(e.entity_type, e.primary_source_id)] = e.canonical_id
    if e.entity_type == "chemical":
        known_ids[("drug", e.primary_source_id)] = e.canonical_id
    if e.entity_type == "haplotype":
        known_ids[("starallele", e.primary_source_id)] = e.canonical_id
        known_ids[("hlaallele", e.primary_source_id)] = e.canonical_id

rels, rel_entities = clinpgx_parser.parse_relationships(known_ids)

# Let's inspect primary_definition IDs vs relationships_only IDs
primary_ids_by_type = defaultdict(set)
for e in primary_entities:
    if e.defined_by == "primary_definition":
        primary_ids_by_type[e.entity_type].add(e.primary_source_id)

# Also check specific files for Haplotypes:
# clinpgxHaplotypes_star_alleles.tsv, clinpgxHaplotypes_named_alleles.tsv, cpic.alleles.json
star_ids = set()
named_ids = set()
import zipfile, csv, io
with zipfile.ZipFile(haplo_dir / "clinpgxHaplotypes.zip") as z:
    r_star = csv.DictReader(io.StringIO(z.read("clinpgxHaplotypes_star_alleles.tsv").decode("utf-8")), delimiter="\t")
    for r in r_star:
        acc = r.get("Accession ID", "").strip()
        if acc: star_ids.add(acc)
    r_named = csv.DictReader(io.StringIO(z.read("clinpgxHaplotypes_named_alleles.tsv").decode("utf-8")), delimiter="\t")
    for r in r_named:
        acc = r.get("Accession ID", "").strip()
        if acc: named_ids.add(acc)

print(f"Star allele IDs in file: {len(star_ids)}")
print(f"Named allele IDs in file: {len(named_ids)}")
print(f"Overlap between star and named: {len(star_ids & named_ids)}")

# Endpoint analysis in relationships.tsv
endpoint_stats = defaultdict(lambda: {"total_occurrences": 0, "unique_ids": set(), "resolved_occurrences": 0, "dangling_occurrences": 0, "resolved_unique_ids": set(), "dangling_unique_ids": set()})

# Also breakdown for Haplotype specifically:
# How many match star_ids only, named_ids only, both?
haplo_star_matches = set()
haplo_named_matches = set()

# Combination of endpoint types for dangling rows
dangling_combinations = Counter()
dangling_row_count = 0
resolved_row_count = 0

for r in rels:
    t1, id1 = r.entity1_type, r.entity1_id
    t2, id2 = r.entity2_type, r.entity2_id
    
    # Check if endpoint 1 is primary_definition
    # Types can be: Gene, Chemical, Variant, Haplotype, StarAllele, HlaAllele, etc.
    res1 = (id1 in primary_ids_by_type.get(t1.lower(), set()))
    if t1.lower() in ("drug", "chemical"):
        res1 = (id1 in primary_ids_by_type.get("chemical", set()))
    elif t1.lower() in ("haplotype", "starallele", "hlaallele"):
        res1 = (id1 in primary_ids_by_type.get("haplotype", set()))
        if id1 in star_ids: haplo_star_matches.add(id1)
        if id1 in named_ids: haplo_named_matches.add(id1)

    res2 = (id2 in primary_ids_by_type.get(t2.lower(), set()))
    if t2.lower() in ("drug", "chemical"):
        res2 = (id2 in primary_ids_by_type.get("chemical", set()))
    elif t2.lower() in ("haplotype", "starallele", "hlaallele"):
        res2 = (id2 in primary_ids_by_type.get("haplotype", set()))
        if id2 in star_ids: haplo_star_matches.add(id2)
        if id2 in named_ids: haplo_named_matches.add(id2)
    
    # Track endpoint 1
    s1 = endpoint_stats[t1]
    s1["total_occurrences"] += 1
    s1["unique_ids"].add(id1)
    if res1:
        s1["resolved_occurrences"] += 1
        s1["resolved_unique_ids"].add(id1)
    else:
        s1["dangling_occurrences"] += 1
        s1["dangling_unique_ids"].add(id1)

    # Track endpoint 2
    s2 = endpoint_stats[t2]
    s2["total_occurrences"] += 1
    s2["unique_ids"].add(id2)
    if res2:
        s2["resolved_occurrences"] += 1
        s2["resolved_unique_ids"].add(id2)
    else:
        s2["dangling_occurrences"] += 1
        s2["dangling_unique_ids"].add(id2)
    
    # Edge level: is dangling if either endpoint is not resolved
    if not (res1 and res2):
        dangling_row_count += 1
        dangling_combinations[(t1, t2)] += 1
    else:
        resolved_row_count += 1

print("\n=== ENDPOINT STATS BY TYPE ===")
print(f"{'Endpoint Type':<25} | {'Unique IDs':<12} | {'Resolved IDs':<12} | {'Dangling IDs':<12} | {'Total Occurrences':<18} | {'Resolved Occ.':<14} | {'Dangling Occ.':<14}")
print("-" * 125)
for t in sorted(endpoint_stats.keys()):
    s = endpoint_stats[t]
    u = len(s["unique_ids"])
    ru = len(s["resolved_unique_ids"])
    du = len(s["dangling_unique_ids"])
    tot = s["total_occurrences"]
    ro = s["resolved_occurrences"]
    do = s["dangling_occurrences"]
    print(f"{t:<25} | {u:<12} | {ru:<12} | {du:<12} | {tot:<18} | {ro:<14} | {do:<14}")

print("\n=== HAPLOTYPE SPECIFIC BREAKDOWN ===")
print(f"Unique Haplotype IDs in relationships: {len(endpoint_stats['Haplotype']['unique_ids'])}")
print(f"Haplotype IDs matching star alleles only: {len(haplo_star_matches - haplo_named_matches)}")
print(f"Haplotype IDs matching named alleles only: {len(haplo_named_matches - haplo_star_matches)}")
print(f"Haplotype IDs matching both star and named: {len(haplo_star_matches & haplo_named_matches)}")
print(f"Total Haplotype IDs matching star OR named: {len(haplo_star_matches | haplo_named_matches)}")
print(f"Haplotype IDs unresolved: {len(endpoint_stats['Haplotype']['unique_ids'] - (haplo_star_matches | haplo_named_matches))}")

print(f"\n=== DANGLING ROWS BY ENDPOINT TYPE COMBINATION ===")
print(f"Total rows in relationships.tsv: {len(rels)}")
print(f"Total resolved relationship rows (both endpoints primary): {resolved_row_count}")
print(f"Total dangling relationship rows (at least 1 endpoint dangling): {dangling_row_count}")
print("\nCombination Breakdown:")
for (t1, t2), cnt in dangling_combinations.most_common():
    print(f"   {t1:<25} <--> {t2:<25} : {cnt:>6} rows")

