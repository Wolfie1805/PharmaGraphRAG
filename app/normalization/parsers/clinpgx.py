"""
ClinPGx parser for Phase 2 data normalization.
Parses in-memory archives, enforces data contracts, tracks raw provenance, and logs rejects.
"""

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

from app.normalization.contracts import (
    EntityRecord,
    CrossReferenceRecord,
    SynonymRecord,
    RelationshipRecord,
    SourceProvenance,
)
from app.normalization.normalize import (
    normalize_text,
    normalize_search_term,
    split_list_field,
)

# License metadata for ClinPGx
CLINPGX_SOURCE_NAME = "ClinPGx"
CLINPGX_LICENSE_TEXT = (
    "Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International license (CC BY-NC-SA 4.0). "
    "NonCommercial use only; under no circumstances can ClinPGx data be sold for other's private or commercial use."
)
CLINPGX_LICENSE_CHECK_DATE = "2026-10-31"

CSV_FIELD_SIZE_LIMIT = 250000
csv.field_size_limit(CSV_FIELD_SIZE_LIMIT)


class ClinPGxParser:
    """Parses ClinPGx core archives and haplotype definitions into validated entities and relationships."""

    def __init__(self, raw_dir: Path, haplo_dir: Path, manifest_run_id: str, haplo_manifest_run_id: str):
        self.raw_dir = raw_dir
        self.haplo_dir = haplo_dir
        self.manifest_run_id = manifest_run_id
        self.haplo_manifest_run_id = haplo_manifest_run_id

        # Raw file SHA-256 cache
        self.file_hashes: Dict[str, str] = {}
        self._compute_file_hashes()

        # Reject log: table_name -> list of dicts
        self.rejects: Dict[str, List[Dict[str, Any]]] = {
            "entities": [],
            "cross_references": [],
            "synonyms": [],
            "relationships": [],
        }

        # Accounting: table_name -> {'raw_rows': int, 'accepted': int, 'rejected': int}
        self.accounting: Dict[str, Dict[str, int]] = {
            "genes": {"raw_rows": 0, "accepted": 0, "rejected": 0},
            "drugs": {"raw_rows": 0, "accepted": 0, "rejected": 0},
            "chemicals": {"raw_rows": 0, "accepted": 0, "rejected": 0},
            "variants": {"raw_rows": 0, "accepted": 0, "rejected": 0},
            "haplotypes_star": {"raw_rows": 0, "accepted": 0, "rejected": 0},
            "haplotypes_named": {"raw_rows": 0, "accepted": 0, "rejected": 0},
            "relationships": {"raw_rows": 0, "accepted": 0, "rejected": 0},
        }

    def _compute_file_hashes(self) -> None:
        """Compute SHA-256 for all archives to guarantee provenance."""
        for p in list(self.raw_dir.glob("*.zip")) + list(self.haplo_dir.glob("*.zip")):
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            self.file_hashes[p.name] = h

    def parse_genes(self) -> Tuple[List[EntityRecord], List[CrossReferenceRecord], List[SynonymRecord]]:
        """Parse genes.tsv into gene entities, cross-references, and synonyms."""
        zip_path = self.raw_dir / "genes.zip"
        archive_sha = self.file_hashes["genes.zip"]

        entities: List[EntityRecord] = []
        xrefs: List[CrossReferenceRecord] = []
        synonyms: List[SynonymRecord] = []

        with zipfile.ZipFile(zip_path, "r") as z:
            content = z.read("genes.tsv").decode("utf-8")
            reader = csv.DictReader(io.StringIO(content), delimiter="\t")
            for idx, r in enumerate(reader, start=1):
                self.accounting["genes"]["raw_rows"] += 1
                acc_id = normalize_text(r.get("PharmGKB Accession Id"))
                symbol = normalize_text(r.get("Symbol"))
                name = normalize_text(r.get("Name"))

                if not acc_id:
                    self.accounting["genes"]["rejected"] += 1
                    self.rejects["entities"].append({
                        "file": "genes.tsv", "row_index": idx, "reason": "EMPTY_PRIMARY_ID", "raw": r
                    })
                    continue

                display_name = symbol if symbol else name
                if not display_name:
                    display_name = acc_id

                prov = SourceProvenance(
                    source_name=CLINPGX_SOURCE_NAME,
                    license_text=CLINPGX_LICENSE_TEXT,
                    license_check_date=CLINPGX_LICENSE_CHECK_DATE,
                    raw_file_path="data/raw/clinpgx/20261030_79ff97e7/genes.zip#genes.tsv",
                    raw_file_sha256=archive_sha,
                    manifest_run_id=self.manifest_run_id,
                    record_index=idx,
                )

                canonical_id = f"pg:gene:{acc_id.replace('PA', '')}"
                ent = EntityRecord(
                    canonical_id=canonical_id,
                    entity_type="gene",
                    primary_source_id=acc_id,
                    display_name=display_name,
                    normalized_name=normalize_search_term(display_name),
                    gene_symbol=symbol if symbol else None,
                    defined_by="primary_definition",
                    provenance=prov,
                )
                entities.append(ent)
                self.accounting["genes"]["accepted"] += 1

                # Cross-references
                raw_xrefs = r.get("Cross-references", "")
                if raw_xrefs:
                    for tok in split_list_field(raw_xrefs):
                        # Typical cross-ref: "NCBI Gene:123" or "Ensembl:ENSG000..."
                        part = tok["text"]
                        if ":" in part:
                            ns, ext_id = part.split(":", 1)
                            xrefs.append(CrossReferenceRecord(
                                canonical_id=canonical_id,
                                namespace=ns.strip().upper().replace(" ", "_"),
                                external_id=ext_id.strip(),
                                provenance=prov,
                            ))

                # Synonyms & Alternative Symbols
                for col_name, syn_type in [("Alternative Names", "alternate_name"), ("Alternative Symbols", "symbol_alias")]:
                    raw_syns = r.get(col_name, "")
                    if raw_syns:
                        for tok in split_list_field(raw_syns):
                            synonyms.append(SynonymRecord(
                                canonical_id=canonical_id,
                                synonym_text=tok["text"],
                                normalized_synonym=normalize_search_term(tok["text"]),
                                synonym_type=syn_type,
                                is_artifact=tok["is_artifact"],
                                is_split_ambiguous=tok["is_split_ambiguous"],
                                provenance=prov,
                            ))

        return entities, xrefs, synonyms

    def parse_chemicals_and_drugs(self) -> Tuple[List[EntityRecord], List[CrossReferenceRecord], List[SynonymRecord]]:
        """Parse chemicals.tsv and drugs.tsv, unifying into canonical pg:chem entities."""
        # 1. Identify all drug accessions
        drug_accs: Set[str] = set()
        drugs_zip = self.raw_dir / "drugs.zip"
        with zipfile.ZipFile(drugs_zip, "r") as z:
            reader = csv.DictReader(io.StringIO(z.read("drugs.tsv").decode("utf-8")), delimiter="\t")
            for idx, r in enumerate(reader, start=1):
                self.accounting["drugs"]["raw_rows"] += 1
                acc = normalize_text(r.get("PharmGKB Accession Id"))
                if acc:
                    drug_accs.add(acc)
                    self.accounting["drugs"]["accepted"] += 1
                else:
                    self.accounting["drugs"]["rejected"] += 1

        # 2. Parse chemicals.tsv as the superset
        chems_zip = self.raw_dir / "chemicals.zip"
        archive_sha = self.file_hashes["chemicals.zip"]

        entities: List[EntityRecord] = []
        xrefs: List[CrossReferenceRecord] = []
        synonyms: List[SynonymRecord] = []

        with zipfile.ZipFile(chems_zip, "r") as z:
            content = z.read("chemicals.tsv").decode("utf-8")
            reader = csv.DictReader(io.StringIO(content), delimiter="\t")
            for idx, r in enumerate(reader, start=1):
                self.accounting["chemicals"]["raw_rows"] += 1
                acc_id = normalize_text(r.get("PharmGKB Accession Id"))
                name = normalize_text(r.get("Name"))

                if not acc_id:
                    self.accounting["chemicals"]["rejected"] += 1
                    self.rejects["entities"].append({
                        "file": "chemicals.tsv", "row_index": idx, "reason": "EMPTY_PRIMARY_ID", "raw": r
                    })
                    continue

                display_name = name if name else acc_id
                is_drug = (acc_id in drug_accs)
                canonical_id = f"pg:chem:{acc_id.replace('PA', '')}"

                prov = SourceProvenance(
                    source_name=CLINPGX_SOURCE_NAME,
                    license_text=CLINPGX_LICENSE_TEXT,
                    license_check_date=CLINPGX_LICENSE_CHECK_DATE,
                    raw_file_path="data/raw/clinpgx/20261030_79ff97e7/chemicals.zip#chemicals.tsv",
                    raw_file_sha256=archive_sha,
                    manifest_run_id=self.manifest_run_id,
                    record_index=idx,
                )

                ent = EntityRecord(
                    canonical_id=canonical_id,
                    entity_type="chemical",
                    primary_source_id=acc_id,
                    display_name=display_name,
                    normalized_name=normalize_search_term(display_name),
                    is_drug=is_drug,
                    defined_by="primary_definition",
                    provenance=prov,
                )
                entities.append(ent)
                self.accounting["chemicals"]["accepted"] += 1

                # Cross-references
                raw_xrefs = r.get("Cross-references", "")
                if raw_xrefs:
                    for tok in split_list_field(raw_xrefs):
                        part = tok["text"]
                        if ":" in part:
                            ns, ext_id = part.split(":", 1)
                            xrefs.append(CrossReferenceRecord(
                                canonical_id=canonical_id,
                                namespace=ns.strip().upper().replace(" ", "_"),
                                external_id=ext_id.strip(),
                                provenance=prov,
                            ))

                # Trade Names & Alternate Names
                for col_name, syn_type in [("Trade Names", "trade_name"), ("Alternate Names", "alternate_name")]:
                    raw_syns = r.get(col_name, "")
                    if raw_syns:
                        for tok in split_list_field(raw_syns):
                            synonyms.append(SynonymRecord(
                                canonical_id=canonical_id,
                                synonym_text=tok["text"],
                                normalized_synonym=normalize_search_term(tok["text"]),
                                synonym_type=syn_type,
                                is_artifact=tok["is_artifact"],
                                is_split_ambiguous=tok["is_split_ambiguous"],
                                provenance=prov,
                            ))

        return entities, xrefs, synonyms

    def parse_variants(self) -> Tuple[List[EntityRecord], List[SynonymRecord]]:
        """Parse variants.tsv into rsID variant entities and synonyms."""
        zip_path = self.raw_dir / "variants.zip"
        archive_sha = self.file_hashes["variants.zip"]

        entities: List[EntityRecord] = []
        synonyms: List[SynonymRecord] = []

        with zipfile.ZipFile(zip_path, "r") as z:
            content = z.read("variants.tsv").decode("utf-8")
            reader = csv.DictReader(io.StringIO(content), delimiter="\t")
            for idx, r in enumerate(reader, start=1):
                self.accounting["variants"]["raw_rows"] += 1
                var_id = normalize_text(r.get("Variant ID"))
                var_name = normalize_text(r.get("Variant Name"))
                gene_symbol = normalize_text(r.get("Gene Symbols"))

                if not var_id:
                    self.accounting["variants"]["rejected"] += 1
                    self.rejects["entities"].append({
                        "file": "variants.tsv", "row_index": idx, "reason": "EMPTY_PRIMARY_ID", "raw": r
                    })
                    continue

                display_name = var_name if var_name else var_id
                canonical_id = f"pg:var:{var_id.replace('PA', '')}"

                prov = SourceProvenance(
                    source_name=CLINPGX_SOURCE_NAME,
                    license_text=CLINPGX_LICENSE_TEXT,
                    license_check_date=CLINPGX_LICENSE_CHECK_DATE,
                    raw_file_path="data/raw/clinpgx/20261030_79ff97e7/variants.zip#variants.tsv",
                    raw_file_sha256=archive_sha,
                    manifest_run_id=self.manifest_run_id,
                    record_index=idx,
                )

                ent = EntityRecord(
                    canonical_id=canonical_id,
                    entity_type="variant",
                    primary_source_id=var_id,
                    display_name=display_name,
                    normalized_name=normalize_search_term(display_name),
                    gene_symbol=gene_symbol if gene_symbol else None,
                    defined_by="primary_definition",
                    provenance=prov,
                )
                entities.append(ent)
                self.accounting["variants"]["accepted"] += 1

                # Synonyms
                raw_syns = r.get("Synonyms", "")
                if raw_syns:
                    for tok in split_list_field(raw_syns):
                        synonyms.append(SynonymRecord(
                            canonical_id=canonical_id,
                            synonym_text=tok["text"],
                            normalized_synonym=normalize_search_term(tok["text"]),
                            synonym_type="variant_synonym",
                            is_artifact=tok["is_artifact"],
                            is_split_ambiguous=tok["is_split_ambiguous"],
                            provenance=prov,
                        ))

        return entities, synonyms

    def parse_haplotypes(self) -> List[EntityRecord]:
        """Parse clinpgxHaplotypes_star_alleles.tsv and clinpgxHaplotypes_named_alleles.tsv."""
        zip_path = self.haplo_dir / "clinpgxHaplotypes.zip"
        archive_sha = self.file_hashes["clinpgxHaplotypes.zip"]

        entities: List[EntityRecord] = []

        with zipfile.ZipFile(zip_path, "r") as z:
            # 1. Star alleles
            content_star = z.read("clinpgxHaplotypes_star_alleles.tsv").decode("utf-8")
            reader_star = csv.DictReader(io.StringIO(content_star), delimiter="\t")
            for idx, r in enumerate(reader_star, start=1):
                self.accounting["haplotypes_star"]["raw_rows"] += 1
                acc_id = normalize_text(r.get("Accession ID"))
                gene = normalize_text(r.get("Gene"))
                allele = normalize_text(r.get("Allele Name"))

                if not acc_id:
                    self.accounting["haplotypes_star"]["rejected"] += 1
                    self.rejects["entities"].append({
                        "file": "clinpgxHaplotypes_star_alleles.tsv", "row_index": idx, "reason": "EMPTY_PRIMARY_ID", "raw": r
                    })
                    continue

                display_name = f"{gene} {allele}" if (gene and allele) else (allele if allele else acc_id)
                canonical_id = f"pg:haplo:{acc_id.replace('PA', '')}"

                prov = SourceProvenance(
                    source_name=CLINPGX_SOURCE_NAME,
                    license_text=CLINPGX_LICENSE_TEXT,
                    license_check_date=CLINPGX_LICENSE_CHECK_DATE,
                    raw_file_path="data/raw/clinpgx/20261031_d2a604a2/clinpgxHaplotypes.zip#clinpgxHaplotypes_star_alleles.tsv",
                    raw_file_sha256=archive_sha,
                    manifest_run_id=self.haplo_manifest_run_id,
                    record_index=idx,
                )

                ent = EntityRecord(
                    canonical_id=canonical_id,
                    entity_type="haplotype",
                    primary_source_id=acc_id,
                    display_name=display_name,
                    normalized_name=normalize_search_term(display_name),
                    gene_symbol=gene if gene else None,
                    defined_by="primary_definition",
                    provenance=prov,
                )
                entities.append(ent)
                self.accounting["haplotypes_star"]["accepted"] += 1

            # 2. Named alleles
            content_named = z.read("clinpgxHaplotypes_named_alleles.tsv").decode("utf-8")
            reader_named = csv.DictReader(io.StringIO(content_named), delimiter="\t")
            for idx, r in enumerate(reader_named, start=1):
                self.accounting["haplotypes_named"]["raw_rows"] += 1
                acc_id = normalize_text(r.get("Accession ID"))
                gene = normalize_text(r.get("Gene"))
                allele = normalize_text(r.get("Allele Name"))

                if not acc_id:
                    self.accounting["haplotypes_named"]["rejected"] += 1
                    self.rejects["entities"].append({
                        "file": "clinpgxHaplotypes_named_alleles.tsv", "row_index": idx, "reason": "EMPTY_PRIMARY_ID", "raw": r
                    })
                    continue

                display_name = f"{gene} {allele}" if (gene and allele) else (allele if allele else acc_id)
                canonical_id = f"pg:haplo:{acc_id.replace('PA', '')}"

                prov = SourceProvenance(
                    source_name=CLINPGX_SOURCE_NAME,
                    license_text=CLINPGX_LICENSE_TEXT,
                    license_check_date=CLINPGX_LICENSE_CHECK_DATE,
                    raw_file_path="data/raw/clinpgx/20261031_d2a604a2/clinpgxHaplotypes.zip#clinpgxHaplotypes_named_alleles.tsv",
                    raw_file_sha256=archive_sha,
                    manifest_run_id=self.haplo_manifest_run_id,
                    record_index=idx,
                )

                ent = EntityRecord(
                    canonical_id=canonical_id,
                    entity_type="haplotype",
                    primary_source_id=acc_id,
                    display_name=display_name,
                    normalized_name=normalize_search_term(display_name),
                    gene_symbol=gene if gene else None,
                    defined_by="primary_definition",
                    provenance=prov,
                )
                entities.append(ent)
                self.accounting["haplotypes_named"]["accepted"] += 1

        return entities

    def parse_relationships(
        self, known_canonical_ids: Dict[Tuple[str, str], str]
    ) -> Tuple[List[RelationshipRecord], List[EntityRecord]]:
        """
        Parse relationships.tsv into RelationshipRecords.
        Dynamically registers relationships_only entities for endpoints lacking dedicated files.
        """
        zip_path = self.raw_dir / "relationships.zip"
        archive_sha = self.file_hashes["relationships.zip"]

        records: List[RelationshipRecord] = []
        relationships_only_entities: Dict[str, EntityRecord] = {}

        with zipfile.ZipFile(zip_path, "r") as z:
            content = z.read("relationships.tsv").decode("utf-8")
            reader = csv.DictReader(io.StringIO(content), delimiter="\t")
            for idx, r in enumerate(reader, start=1):
                self.accounting["relationships"]["raw_rows"] += 1
                t1 = normalize_text(r.get("Entity1_type"))
                id1 = normalize_text(r.get("Entity1_id"))
                n1 = normalize_text(r.get("Entity1_name"))
                t2 = normalize_text(r.get("Entity2_type"))
                id2 = normalize_text(r.get("Entity2_id"))
                n2 = normalize_text(r.get("Entity2_name"))
                assoc = normalize_text(r.get("Association"))
                raw_pmids = r.get("PMIDs", "")

                if not (id1 and id2 and t1 and t2):
                    self.accounting["relationships"]["rejected"] += 1
                    self.rejects["relationships"].append({
                        "file": "relationships.tsv", "row_index": idx, "reason": "EMPTY_PRIMARY_ID", "raw": r
                    })
                    continue

                prov = SourceProvenance(
                    source_name=CLINPGX_SOURCE_NAME,
                    license_text=CLINPGX_LICENSE_TEXT,
                    license_check_date=CLINPGX_LICENSE_CHECK_DATE,
                    raw_file_path="data/raw/clinpgx/20261030_79ff97e7/relationships.zip#relationships.tsv",
                    raw_file_sha256=archive_sha,
                    manifest_run_id=self.manifest_run_id,
                    record_index=idx,
                )

                # Resolve canonical IDs or create relationships_only entity
                cid1 = known_canonical_ids.get((t1.lower(), id1))
                if not cid1:
                    # Register relationships_only entity
                    ent_type1 = "snv" if t1 == "SNV" else ("phenotype" if t1 == "Phenotype" else ("cnv" if "CopyNumber" in t1 else "haplotype"))
                    canonical_id1 = f"pg:{ent_type1}:{id1.replace('PA', '')}"
                    if id1 not in relationships_only_entities:
                        relationships_only_entities[id1] = EntityRecord(
                            canonical_id=canonical_id1,
                            entity_type=ent_type1,  # type: ignore
                            primary_source_id=id1,
                            display_name=n1 if n1 else id1,
                            normalized_name=normalize_search_term(n1 if n1 else id1),
                            defined_by="relationships_only",
                            provenance=prov,
                        )
                    cid1 = canonical_id1

                cid2 = known_canonical_ids.get((t2.lower(), id2))
                if not cid2:
                    ent_type2 = "snv" if t2 == "SNV" else ("phenotype" if t2 == "Phenotype" else ("cnv" if "CopyNumber" in t2 else "haplotype"))
                    canonical_id2 = f"pg:{ent_type2}:{id2.replace('PA', '')}"
                    if id2 not in relationships_only_entities:
                        relationships_only_entities[id2] = EntityRecord(
                            canonical_id=canonical_id2,
                            entity_type=ent_type2,  # type: ignore
                            primary_source_id=id2,
                            display_name=n2 if n2 else id2,
                            normalized_name=normalize_search_term(n2 if n2 else id2),
                            defined_by="relationships_only",
                            provenance=prov,
                        )
                    cid2 = canonical_id2

                # Flag dangling if either endpoint was relationships_only
                is_dang = (id1 in relationships_only_entities or id2 in relationships_only_entities)

                # Deterministic rel hash
                rel_hash = hashlib.md5(f"{id1}|{id2}|{assoc}".encode("utf-8")).hexdigest()
                pmids = [p.strip() for p in raw_pmids.split(",") if p.strip()] if raw_pmids else []

                rec = RelationshipRecord(
                    relationship_id=f"rel:{rel_hash}",
                    entity1_id=id1,
                    entity1_name=n1,
                    entity1_type=t1,
                    entity1_canonical_id=cid1,
                    entity2_id=id2,
                    entity2_name=n2,
                    entity2_type=t2,
                    entity2_canonical_id=cid2,
                    association=assoc,
                    pmids=pmids,
                    is_dangling=is_dang,
                    provenance=prov,
                )
                records.append(rec)
                self.accounting["relationships"]["accepted"] += 1

        return records, list(relationships_only_entities.values())

