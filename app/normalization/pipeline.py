"""
Execution pipeline for Phase 2 data normalization.
Runs parsers, enforces deterministic serialization, logs rejects, and produces Parquet tables.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
import pyarrow as pa
import pyarrow.parquet as pq

from app.normalization.contracts import (
    EntityRecord,
    CrossReferenceRecord,
    SynonymRecord,
    RelationshipRecord,
    PublicationRecord,
)
from app.normalization.parsers.clinpgx import ClinPGxParser
from app.normalization.parsers.cpic import CPICParser
from app.normalization.parsers.pubmed import PubMedParser

PARQUET_ROW_GROUP_SIZE = 50000
PARQUET_COMPRESSION = "SNAPPY"


def run_normalization_pipeline(
    output_dir: Path,
    clinpgx_raw_dir: Path = Path("data/raw/clinpgx/20261030_79ff97e7"),
    haplo_raw_dir: Path = Path("data/raw/clinpgx/20261031_d2a604a2"),
    pubmed_manifest: Path = Path("data/manifests/manifest_pubmed_20261031_7d1398e0.json"),
    clinpgx_manifest_id: str = "20261030_79ff97e7",
    haplo_manifest_id: str = "20261031_d2a604a2",
) -> Dict[str, Any]:
    """Execute complete Phase 2 normalization pipeline."""
    output_dir.mkdir(parents=True, exist_ok=True)
    review_dir = Path("data/review")
    review_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initialize parsers
    clinpgx_parser = ClinPGxParser(clinpgx_raw_dir, haplo_raw_dir, clinpgx_manifest_id, haplo_manifest_id)
    cpic_parser = CPICParser(haplo_raw_dir / "cpic.alleles.json", haplo_manifest_id)
    pubmed_parser = PubMedParser(pubmed_manifest)

    # 2. Parse primary entities
    print("  -> Parsing genes...", flush=True)
    gene_entities, gene_xrefs, gene_syns = clinpgx_parser.parse_genes()
    print("  -> Parsing chemicals and drugs...", flush=True)
    chem_entities, chem_xrefs, chem_syns = clinpgx_parser.parse_chemicals_and_drugs()
    print("  -> Parsing variants...", flush=True)
    var_entities, var_syns = clinpgx_parser.parse_variants()
    print("  -> Parsing haplotypes...", flush=True)
    haplo_entities = clinpgx_parser.parse_haplotypes()
    print("  -> Parsing CPIC alleles...", flush=True)
    cpic_entities = cpic_parser.parse_alleles()

    all_primary_entities: List[EntityRecord] = (
        gene_entities + chem_entities + var_entities + haplo_entities + cpic_entities
    )

    # Build canonical ID lookup map: (type, primary_source_id) -> canonical_id
    known_ids: Dict[Tuple[str, str], str] = {}
    for e in all_primary_entities:
        known_ids[(e.entity_type, e.primary_source_id)] = e.canonical_id
        # Also map type variants
        if e.entity_type == "chemical":
            known_ids[("drug", e.primary_source_id)] = e.canonical_id
        if e.entity_type == "haplotype":
            known_ids[("starallele", e.primary_source_id)] = e.canonical_id
            known_ids[("hlaallele", e.primary_source_id)] = e.canonical_id

    # 3. Parse relationships (with relationships_only entity generation)
    print("  -> Parsing relationships...", flush=True)
    relationships, rel_entities = clinpgx_parser.parse_relationships(known_ids)

    # Combine all entities
    all_entities = all_primary_entities + rel_entities
    all_xrefs = gene_xrefs + chem_xrefs
    all_synonyms = gene_syns + chem_syns + var_syns

    # 4. Parse PubMed publications
    print("  -> Parsing PubMed XML batches...", flush=True)
    publications = pubmed_parser.parse_all_batches()

    # 5. Serialization with deterministic sorting and explicit PyArrow schemas
    print("  -> Serializing tables to Parquet...", flush=True)
    # A. Entities
    entity_dicts = [
        {
            "canonical_id": e.canonical_id,
            "entity_type": e.entity_type,
            "primary_source_id": e.primary_source_id,
            "display_name": e.display_name,
            "normalized_name": e.normalized_name,
            "is_drug": e.is_drug,
            "gene_symbol": e.gene_symbol or "",
            "defined_by": e.defined_by,
            "is_ambiguous": e.is_ambiguous,
            "is_artifact": e.is_artifact,
            "source_name": e.provenance.source_name,
            "raw_file_sha256": e.provenance.raw_file_sha256,
        }
        for e in all_entities
    ]
    entity_dicts.sort(key=lambda x: (x["canonical_id"], x["primary_source_id"]))

    ent_schema = pa.schema([
        ("canonical_id", pa.string()),
        ("entity_type", pa.string()),
        ("primary_source_id", pa.string()),
        ("display_name", pa.string()),
        ("normalized_name", pa.string()),
        ("is_drug", pa.bool_()),
        ("gene_symbol", pa.string()),
        ("defined_by", pa.string()),
        ("is_ambiguous", pa.bool_()),
        ("is_artifact", pa.bool_()),
        ("source_name", pa.string()),
        ("raw_file_sha256", pa.string()),
    ])
    ent_table = pa.Table.from_pylist(entity_dicts, schema=ent_schema)
    ent_path = output_dir / "entities.parquet"
    pq.write_table(ent_table, ent_path, compression=PARQUET_COMPRESSION, row_group_size=PARQUET_ROW_GROUP_SIZE)

    # B. Cross-references
    xref_dicts = [
        {
            "canonical_id": x.canonical_id,
            "namespace": x.namespace,
            "external_id": x.external_id,
            "raw_file_sha256": x.provenance.raw_file_sha256,
        }
        for x in all_xrefs
    ]
    xref_dicts.sort(key=lambda x: (x["canonical_id"], x["namespace"], x["external_id"]))
    xref_schema = pa.schema([
        ("canonical_id", pa.string()),
        ("namespace", pa.string()),
        ("external_id", pa.string()),
        ("raw_file_sha256", pa.string()),
    ])
    xref_table = pa.Table.from_pylist(xref_dicts, schema=xref_schema)
    xref_path = output_dir / "cross_references.parquet"
    pq.write_table(xref_table, xref_path, compression=PARQUET_COMPRESSION, row_group_size=PARQUET_ROW_GROUP_SIZE)

    # C. Synonyms
    syn_dicts = [
        {
            "canonical_id": s.canonical_id,
            "synonym_text": s.synonym_text,
            "normalized_synonym": s.normalized_synonym,
            "synonym_type": s.synonym_type,
            "is_ambiguous": s.is_ambiguous,
            "is_artifact": s.is_artifact,
            "is_split_ambiguous": s.is_split_ambiguous,
            "raw_file_sha256": s.provenance.raw_file_sha256,
        }
        for s in all_synonyms
    ]
    syn_dicts.sort(key=lambda x: (x["canonical_id"], x["normalized_synonym"], x["synonym_text"]))
    syn_schema = pa.schema([
        ("canonical_id", pa.string()),
        ("synonym_text", pa.string()),
        ("normalized_synonym", pa.string()),
        ("synonym_type", pa.string()),
        ("is_ambiguous", pa.bool_()),
        ("is_artifact", pa.bool_()),
        ("is_split_ambiguous", pa.bool_()),
        ("raw_file_sha256", pa.string()),
    ])
    syn_table = pa.Table.from_pylist(syn_dicts, schema=syn_schema)
    syn_path = output_dir / "synonyms.parquet"
    pq.write_table(syn_table, syn_path, compression=PARQUET_COMPRESSION, row_group_size=PARQUET_ROW_GROUP_SIZE)

    # D. Relationships
    rel_dicts = [
        {
            "relationship_id": r.relationship_id,
            "entity1_id": r.entity1_id,
            "entity1_name": r.entity1_name,
            "entity1_type": r.entity1_type,
            "entity1_canonical_id": r.entity1_canonical_id or "",
            "entity2_id": r.entity2_id,
            "entity2_name": r.entity2_name,
            "entity2_type": r.entity2_type,
            "entity2_canonical_id": r.entity2_canonical_id or "",
            "association": r.association,
            "pmids": r.pmids,
            "is_dangling": r.is_dangling,
            "raw_file_sha256": r.provenance.raw_file_sha256,
        }
        for r in relationships
    ]
    rel_dicts.sort(key=lambda x: x["relationship_id"])
    rel_schema = pa.schema([
        ("relationship_id", pa.string()),
        ("entity1_id", pa.string()),
        ("entity1_name", pa.string()),
        ("entity1_type", pa.string()),
        ("entity1_canonical_id", pa.string()),
        ("entity2_id", pa.string()),
        ("entity2_name", pa.string()),
        ("entity2_type", pa.string()),
        ("entity2_canonical_id", pa.string()),
        ("association", pa.string()),
        ("pmids", pa.list_(pa.string())),
        ("is_dangling", pa.bool_()),
        ("raw_file_sha256", pa.string()),
    ])
    rel_table = pa.Table.from_pylist(rel_dicts, schema=rel_schema)
    rel_path = output_dir / "relationships.parquet"
    pq.write_table(rel_table, rel_path, compression=PARQUET_COMPRESSION, row_group_size=PARQUET_ROW_GROUP_SIZE)

    # E. Publications
    pub_dicts = [
        {
            "pmid": p.pmid,
            "record_type": p.record_type,
            "title": p.title,
            "journal_or_book": p.journal_or_book,
            "pubdate_iso": p.pubdate_iso,
            "date_precision": p.date_precision,
            "doi": p.doi or "",
            "abstract_text": p.abstract_text,
            "abstract_structured": p.abstract_structured,
            "abstract_sections": p.abstract_sections or "",
            "mesh_terms": p.mesh_terms,
            "raw_file_sha256": p.provenance.raw_file_sha256,
        }
        for p in publications
    ]
    pub_dicts.sort(key=lambda x: x["pmid"])
    pub_schema = pa.schema([
        ("pmid", pa.string()),
        ("record_type", pa.string()),
        ("title", pa.string()),
        ("journal_or_book", pa.string()),
        ("pubdate_iso", pa.string()),
        ("date_precision", pa.string()),
        ("doi", pa.string()),
        ("abstract_text", pa.string()),
        ("abstract_structured", pa.bool_()),
        ("abstract_sections", pa.string()),
        ("mesh_terms", pa.list_(pa.string())),
        ("raw_file_sha256", pa.string()),
    ])
    pub_table = pa.Table.from_pylist(pub_dicts, schema=pub_schema)
    pub_path = output_dir / "publications.parquet"
    pq.write_table(pub_table, pub_path, compression=PARQUET_COMPRESSION, row_group_size=PARQUET_ROW_GROUP_SIZE)

    # 6. Rejects Logging
    all_rejects = {
        **clinpgx_parser.rejects,
        "cpic_alleles": cpic_parser.rejects,
        "publications": pubmed_parser.rejects,
    }
    for name, rej_list in all_rejects.items():
        rej_file = output_dir / f"{name}.rejects.jsonl"
        with open(rej_file, "w", encoding="utf-8") as f:
            for r in rej_list:
                f.write(json.dumps(r) + "\n")

    # 7. Summary Accounting
    accounting = {
        **clinpgx_parser.accounting,
        "cpic_alleles": cpic_parser.accounting,
        "pubmed": pubmed_parser.accounting,
    }

    # Compute hashes of produced Parquet files
    parquet_hashes = {
        "entities.parquet": hashlib.sha256(ent_path.read_bytes()).hexdigest(),
        "cross_references.parquet": hashlib.sha256(xref_path.read_bytes()).hexdigest(),
        "synonyms.parquet": hashlib.sha256(syn_path.read_bytes()).hexdigest(),
        "relationships.parquet": hashlib.sha256(rel_path.read_bytes()).hexdigest(),
        "publications.parquet": hashlib.sha256(pub_path.read_bytes()).hexdigest(),
    }

    return {
        "accounting": accounting,
        "parquet_hashes": parquet_hashes,
        "table_counts": {
            "entities": len(all_entities),
            "cross_references": len(all_xrefs),
            "synonyms": len(all_synonyms),
            "relationships": len(relationships),
            "publications": len(publications),
        },
    }
