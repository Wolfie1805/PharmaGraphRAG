"""Tests for ClinPGx acquisition connector with mocked HTTP (strictly offline)."""

import json
from pathlib import Path
import httpx
import pytest
import respx

from app.config.model import ClinPGxConfig, StorageConfig
from app.ingestion.clinpgx import acquire_clinpgx


MOCK_CATALOG = {
    "status": "success",
    "data": [
        {
            "fileName": "genes.zip",
            "lastModified": "2026-10-05T00:37:03-07:00",
            "path": "data/genes.zip",
            "size": 1024,
        },
        {
            "fileName": "drugs.zip",
            "lastModified": "2026-10-05T00:29:09-07:00",
            "path": "data/drugs.zip",
            "size": 512,
        },
    ],
}


@respx.mock
def test_acquire_clinpgx_mocked(tmp_path):
    base_url = "https://api.clinpgx.org/v1"
    config = ClinPGxConfig(
        base_url=base_url,
        catalog_endpoint="/data/file/data/?view=min",
        download_endpoint_template="/download/file/data/{file_name}",
        request_delay_seconds=0.0,
        selected_files=["genes.zip", "drugs.zip"],
    )
    storage = StorageConfig(raw_dir=Path("raw"), manifests_dir=Path("manifests"))

    # Mock catalog
    respx.get(f"{base_url}/data/file/data/?view=min").respond(json=MOCK_CATALOG)
    # Mock file downloads
    respx.get(f"{base_url}/download/file/data/genes.zip").respond(
        content=b"PK\x03\x04mock_genes_zip_bytes",
        headers={"Content-Type": "application/zip"},
    )
    respx.get(f"{base_url}/download/file/data/drugs.zip").respond(
        content=b"PK\x03\x04mock_drugs_zip_bytes",
        headers={"Content-Type": "application/zip"},
    )

    client = httpx.Client()
    manifest, manifest_path = acquire_clinpgx(
        config=config,
        storage=storage,
        workspace_root=tmp_path,
        client=client,
    )

    assert manifest.run_status == "complete"
    assert manifest.source_name == "ClinPGx"
    assert manifest.release_date_as_shown == "2026-10-05T00:37:03-07:00"
    assert manifest.source_version == "2026-10-05"
    assert manifest.license_name == "CC BY-SA 4.0"

    # Total files in manifest: catalog snapshot + 2 archives = 3
    assert len(manifest.files) == 3
    file_names = [f.relative_path.split("/")[-1] for f in manifest.files]
    assert "clinpgx_file_catalog.json" in file_names
    assert "genes.zip" in file_names
    assert "drugs.zip" in file_names

    # Check that zip archives were not unzipped
    for entry in manifest.files:
        p = tmp_path / entry.relative_path
        assert p.is_file()
        assert p.stat().st_size == entry.byte_size

