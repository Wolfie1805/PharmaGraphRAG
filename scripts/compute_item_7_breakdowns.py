"""
Compute breakdowns for Item 7:
- entities by entity_type and defined_by
- cross_references by namespace
- synonyms by synonym_type
- verify data/processed contents and DVC
"""

import sys
from collections import Counter
from pathlib import Path

from app.normalization.parsers.clinpgx import ClinPGxParser
from app.normalization.parsers.cpic import CPICParser

sys.stdout.reconfigure(encoding="utf-8")

raw_dir = Path("data/raw/clinpgx/20261030_79ff97e7")
haplo_dir = Path("data/raw/clinpgx/20261031_d2a604a2")

clinpgx_parser = ClinPGxParser(raw_dir, haplo_dir, "20261030_79ff97e7", "20261031_d2a604a2")
cpic_parser = CPICParser(haplo_dir / "cpic.alleles.json", "20261031_d2a604a2")

genes, g_xrefs, g_syns = clinpgx_parser.parse_genes()
chems, c_xrefs, c_syns = clinpgx_parser.parse_chemicals_and_drugs()
vars_, v_syns = clinpgx_parser.parse_variants()
haplos = clinpgx_parser.parse_haplotypes()
cpic = cpic_parser.parse_alleles()

primary_entities = genes + chems + vars_ + haplos + cpic

known_ids = {}
for e in primary_entities:
    known_ids[(e.entity_type, e.primary_source_id)] = e.canonical_id
    if e.entity_type == "chemical":
        known_ids[("drug", e.primary_source_id)] = e.canonical_id
    if e.entity_type == "haplotype":
        known_ids[("starallele", e.primary_source_id)] = e.canonical_id
        known_ids[("hlaallele", e.primary_source_id)] = e.canonical_id

rels, rel_entities = clinpgx_parser.parse_relationships(known_ids)
all_entities = primary_entities + rel_entities
all_xrefs = g_xrefs + c_xrefs
all_syns = g_syns + c_syns + v_syns

print("=== 1. ENTITIES BY ENTITY_TYPE AND DEFINED_BY ===")
ent_counts = Counter((e.entity_type, e.defined_by) for e in all_entities)
print(f"{'Entity Type':<15} | {'Defined By':<22} | {'Count':<8}")
print("-" * 50)
total_ents = 0
for (etype, def_by), cnt in sorted(ent_counts.items()):
    total_ents += cnt
    print(f"{etype:<15} | {def_by:<22} | {cnt:<8}")
print("-" * 50)
print(f"{'TOTAL':<15} | {'':<22} | {total_ents:<8}")

print("\n=== 2. CROSS REFERENCES BY NAMESPACE ===")
xref_counts = Counter(x.namespace for x in all_xrefs)
print(f"{'Namespace':<25} | {'Count':<8}")
print("-" * 36)
total_xrefs = 0
for ns, cnt in xref_counts.most_common():
    total_xrefs += cnt
    print(f"{ns:<25} | {cnt:<8}")
print("-" * 36)
print(f"{'TOTAL':<25} | {total_xrefs:<8}")

print("\n=== 3. SYNONYMS BY SYNONYM_TYPE ===")
syn_counts = Counter(s.synonym_type for s in all_syns)
print(f"{'Synonym Type':<25} | {'Count':<8}")
print("-" * 36)
total_syns = 0
for stype, cnt in syn_counts.most_common():
    total_syns += cnt
    print(f"{stype:<25} | {cnt:<8}")
print("-" * 36)
print(f"{'TOTAL':<25} | {total_syns:<8}")

