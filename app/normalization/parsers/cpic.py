"""
CPIC parser for Phase 2 data normalization.
Parses cpic.alleles.json, carries dedicated CC0 1.0 license metadata, and enforces contracts.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Any

from app.normalization.contracts import EntityRecord, SourceProvenance
from app.normalization.normalize import normalize_text, normalize_search_term

CPIC_SOURCE_NAME = "CPIC"
CPIC_LICENSE_TEXT = (
    "Creative Commons Zero 1.0 Universal (CC0 1.0) Public Domain Dedication. "
    "CPIC has waived all copyright and related rights to CPIC guidelines and associated data tables."
)
CPIC_LICENSE_CHECK_DATE = "2026-10-31"


class CPICParser:
    """Parses cpic.alleles.json into validated canonical haplotype/allele EntityRecords."""

    def __init__(self, json_path: Path, manifest_run_id: str):
        self.json_path = json_path
        self.manifest_run_id = manifest_run_id
        self.file_sha256 = hashlib.sha256(self.json_path.read_bytes()).hexdigest()

        self.rejects: List[Dict[str, Any]] = []
        self.accounting = {"raw_rows": 0, "accepted": 0, "rejected": 0}

    def parse_alleles(self) -> List[EntityRecord]:
        """Parse all allele objects from cpic.alleles.json."""
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entities: List[EntityRecord] = []
        for idx, item in enumerate(data, start=1):
            self.accounting["raw_rows"] += 1
            allele_obj = item.get("allele", {})
            acc_id = normalize_text(allele_obj.get("accessionId"))
            allele_name = normalize_text(allele_obj.get("name"))
            gene_symbol = normalize_text(allele_obj.get("gene", {}).get("symbol"))

            if not acc_id:
                self.accounting["rejected"] += 1
                self.rejects.append({
                    "file": "cpic.alleles.json", "row_index": idx, "reason": "EMPTY_PRIMARY_ID", "raw": item
                })
                continue

            display_name = f"{gene_symbol} {allele_name}" if (gene_symbol and allele_name) else (allele_name if allele_name else acc_id)
            canonical_id = f"pg:haplo:{acc_id.replace('PA', '')}"

            prov = SourceProvenance(
                source_name=CPIC_SOURCE_NAME,
                license_text=CPIC_LICENSE_TEXT,
                license_check_date=CPIC_LICENSE_CHECK_DATE,
                raw_file_path="data/raw/clinpgx/20261031_d2a604a2/cpic.alleles.json",
                raw_file_sha256=self.file_sha256,
                manifest_run_id=self.manifest_run_id,
                record_index=idx,
            )

            ent = EntityRecord(
                canonical_id=canonical_id,
                entity_type="haplotype",
                primary_source_id=acc_id,
                display_name=display_name,
                normalized_name=normalize_search_term(display_name),
                gene_symbol=gene_symbol if gene_symbol else None,
                defined_by="primary_definition",
                provenance=prov,
            )
            entities.append(ent)
            self.accounting["accepted"] += 1

        return entities

