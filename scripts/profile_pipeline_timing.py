"""
Profile execution timing of normalization steps.
"""

import sys
import time
from pathlib import Path

from app.normalization.parsers.clinpgx import ClinPGxParser
from app.normalization.parsers.cpic import CPICParser
from app.normalization.parsers.pubmed import PubMedParser

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

clinpgx_raw_dir = Path("data/raw/clinpgx/20261030_79ff97e7")
haplo_raw_dir = Path("data/raw/clinpgx/20261031_d2a604a2")
pubmed_manifest = Path("data/manifests/manifest_pubmed_20261031_7d1398e0.json")

print("Initializing parsers...", flush=True)
t0 = time.time()
clinpgx_parser = ClinPGxParser(clinpgx_raw_dir, haplo_raw_dir, "20261030_79ff97e7", "20261031_d2a604a2")
cpic_parser = CPICParser(haplo_raw_dir / "cpic.alleles.json", "20261031_d2a604a2")
pubmed_parser = PubMedParser(pubmed_manifest)
print(f"Init took: {time.time() - t0:.2f}s", flush=True)

t = time.time()
genes, x1, s1 = clinpgx_parser.parse_genes()
print(f"Genes ({len(genes)}): {time.time() - t:.2f}s", flush=True)

t = time.time()
chems, x2, s2 = clinpgx_parser.parse_chemicals_and_drugs()
print(f"Chemicals ({len(chems)}): {time.time() - t:.2f}s", flush=True)

t = time.time()
vars_, s3 = clinpgx_parser.parse_variants()
print(f"Variants ({len(vars_)}): {time.time() - t:.2f}s", flush=True)

t = time.time()
haplos = clinpgx_parser.parse_haplotypes()
print(f"Haplotypes ({len(haplos)}): {time.time() - t:.2f}s", flush=True)

t = time.time()
cpic = cpic_parser.parse_alleles()
print(f"CPIC ({len(cpic)}): {time.time() - t:.2f}s", flush=True)

known_ids = {}
for e in genes + chems + vars_ + haplos + cpic:
    known_ids[(e.entity_type, e.primary_source_id)] = e.canonical_id
    if e.entity_type == "chemical":
        known_ids[("drug", e.primary_source_id)] = e.canonical_id
    if e.entity_type == "haplotype":
        known_ids[("starallele", e.primary_source_id)] = e.canonical_id
        known_ids[("hlaallele", e.primary_source_id)] = e.canonical_id

t = time.time()
rels, rel_ents = clinpgx_parser.parse_relationships(known_ids)
print(f"Relationships ({len(rels)} rels, {len(rel_ents)} ents): {time.time() - t:.2f}s", flush=True)

t = time.time()
pubs = pubmed_parser.parse_all_batches()
print(f"PubMed ({len(pubs)}): {time.time() - t:.2f}s", flush=True)

