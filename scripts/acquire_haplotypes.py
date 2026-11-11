"""Acquire confirmed haplotype and allele definition files into raw directory."""

from pathlib import Path

from app.config.model import ClinPGxConfig, StorageConfig
from app.ingestion.clinpgx import acquire_clinpgx

config = ClinPGxConfig(
    base_url="https://api.clinpgx.org/v1",
    catalog_endpoint="/data/file/data/?view=min",
    download_endpoint_template="/download/file/data/{file_name}",
    request_delay_seconds=0.5,
    selected_files=[
        "clinpgxHaplotypes.zip",
        "cpic.alleles.json",
    ],
)
storage = StorageConfig(raw_dir=Path("data/raw"), manifests_dir=Path("data/manifests"))

manifest, manifest_path = acquire_clinpgx(config=config, storage=storage, workspace_root=Path("."))
print(f"Acquisition complete! Run ID: {manifest.run_id}")
print(f"Manifest written to: {manifest_path}")
print(f"Files acquired: {len(manifest.files)}")
for f in manifest.files:
    print(f"  - {f.relative_path} ({f.byte_size} bytes, SHA-256: {f.sha256})")

