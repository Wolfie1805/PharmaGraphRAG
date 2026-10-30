"""PharmaGraph Run Manifest Models & Serialization.

Adheres strictly to Phase 1 Task 2 requirements:
- Immutable run manifests saved as JSON under data/manifests/
- Full file hashes (SHA-256), byte sizes, UTC timestamps, git commit
- Provenance tracking (PMID to query ids, esearch counts, exact query strings)
- Missing PMID reconciliation logging (never silently dropped)
- Zero secrets in manifests
"""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class ManifestFileEntry(BaseModel):
    relative_path: str = Field(description="Relative path of file from workspace root")
    byte_size: int = Field(ge=0, description="Exact file size in bytes")
    sha256: str = Field(min_length=64, max_length=64, description="Hex-encoded SHA-256 hash")
    record_count: Optional[int] = Field(default=None, description="Record count if cheaply known")


class BaseRunManifest(BaseModel):
    run_id: str = Field(description="Unique run identifier (e.g. UTC date_uuid)")
    source_name: str = Field(description="Name of source, e.g. ClinPGx or PubMed")
    endpoint_url: str = Field(description="Endpoint or catalog URL (secrets redacted)")
    retrieval_timestamp_utc: str = Field(description="ISO 8601 UTC timestamp")
    source_version: str = Field(description="Version or release date as source shows it or 'not provided'")
    license_name: str = Field(description="License identifier, e.g. CC BY-SA 4.0")
    license_url: str = Field(description="Official URL for the license")
    license_checked_date: str = Field(description="ISO date when license was verified")
    git_commit: str = Field(description="HEAD git commit hash of code that generated run")
    run_status: RunStatus = Field(default=RunStatus.INCOMPLETE)
    notes: Optional[str] = None
    files: list[ManifestFileEntry] = Field(default_factory=list)

    def save(self, manifests_dir: Path | str) -> Path:
        """Atomically save manifest as JSON in the manifests directory."""
        target_dir = Path(manifests_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = target_dir / f"manifest_{self.source_name.lower()}_{self.run_id}.json"
        temp_path = manifest_path.with_suffix(".tmp")
        temp_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        import os
        os.replace(temp_path, manifest_path)
        return manifest_path


class ReconciliationResult(BaseModel):
    total_requested: int
    total_received: int
    missing_count: int
    missing_pmids: list[str] = Field(default_factory=list)
    reconciled: bool = True


class PubMedRunManifest(BaseRunManifest):
    source_name: str = "PubMed"
    database_name: str = "pubmed"
    is_pilot: bool = False
    pilot_selection_rule: Optional[str] = None
    queries: dict[str, str] = Field(default_factory=dict, description="query_id -> exact query string")
    esearch_counts: dict[str, int] = Field(default_factory=dict, description="query_id -> reported esearch count")
    pmids_retrieved: list[str] = Field(default_factory=list, description="Deduplicated list of PMIDs retrieved")
    batch_size: int = 200
    pmid_to_queries: dict[str, list[str]] = Field(default_factory=dict, description="PMID -> list of query_ids matching it")
    reconciliation: Optional[ReconciliationResult] = None


class ClinPGxRunManifest(BaseRunManifest):
    source_name: str = "ClinPGx"
    release_date_as_shown: str
    catalog_snapshot_file: Optional[str] = None
    discrepancy_notes: Optional[str] = None


def get_current_utc_timestamp() -> str:
    """Return ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()

