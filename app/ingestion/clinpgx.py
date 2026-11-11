"""ClinPGx / PharmGKB Raw Data Acquisition Connector.

Strictly follows Phase 1 rules:
- Downloads raw archives without modification or unzipping
- Saves catalog snapshot as a raw artifact
- Raw immutability (write to temporary file, atomic rename)
- Records license, version, git commit, and full SHA-256 hashes
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import certifi
import httpx

from app.config.manifest import ClinPGxRunManifest, ManifestFileEntry, RunStatus
from app.config.model import ClinPGxConfig, StorageConfig
from app.ingestion.git_utils import get_git_commit_hash
from app.ingestion.hash_utils import compute_sha256, write_raw_file_atomically
from app.ingestion.retry import execute_with_retry

logger = logging.getLogger(__name__)

USER_AGENT = "PharmaGraph-Research/0.1.0 (+https://github.com/PharmaGraph)"


class ClinPGxAcquisitionError(Exception):
    """Raised when ClinPGx download or verification fails."""
    pass


def acquire_clinpgx(
    config: ClinPGxConfig,
    storage: StorageConfig,
    workspace_root: Path = Path("."),
    client: httpx.Client | None = None,
) -> tuple[ClinPGxRunManifest, Path]:
    """Execute raw acquisition of confirmed ClinPGx datasets."""
    run_date = datetime.now(timezone.utc).strftime("%Y%m%d")
    run_id = f"{run_date}_{uuid.uuid4().hex[:8]}"
    raw_run_dir = workspace_root / storage.raw_dir / "clinpgx" / run_id
    raw_run_dir.mkdir(parents=True, exist_ok=True)

    git_commit = get_git_commit_hash(workspace_root)
    utc_timestamp = datetime.now(timezone.utc).isoformat()

    manifest = ClinPGxRunManifest(
        run_id=run_id,
        source_name="ClinPGx",
        endpoint_url=f"{config.base_url}{config.catalog_endpoint}",
        retrieval_timestamp_utc=utc_timestamp,
        source_version="not provided",
        release_date_as_shown="2026-10-05",
        license_name="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        license_checked_date="2026-10-30",
        git_commit=git_commit,
        run_status=RunStatus.INCOMPLETE,
        discrepancy_notes=(
            "UI states 'These files are generated on the 6th of every month.' "
            "whereas catalog file metadata records lastModified timestamps as 2026-10-05."
        ),
        files=[],
    )

    should_close_client = False
    if client is None:
        client = httpx.Client(
            verify=certifi.where(),
            headers={"User-Agent": USER_AGENT},
            timeout=60.0,
            follow_redirects=True,
        )
        should_close_client = True

    try:
        # Step 1: Fetch and save catalog API snapshot as a raw artifact
        catalog_url = f"{config.base_url}{config.catalog_endpoint}"
        logger.info("Fetching ClinPGx file catalog from %s", catalog_url)

        def fetch_catalog() -> httpx.Response:
            return client.get(catalog_url)

        catalog_resp = execute_with_retry(fetch_catalog)
        catalog_data = catalog_resp.json()

        # Extract source release date from files in catalog
        catalog_items = catalog_data.get("data", [])
        if catalog_items:
            selected_dates = [
                item.get("lastModified")
                for item in catalog_items
                if item.get("fileName") in config.selected_files and item.get("lastModified")
            ]
            last_mod = (
                max(selected_dates)
                if selected_dates
                else catalog_items[0].get("lastModified", "2026-10-05")
            )
            manifest.source_version = last_mod.split("T")[0]
            manifest.release_date_as_shown = last_mod

        # Save catalog raw artifact
        catalog_file_path = raw_run_dir / "clinpgx_file_catalog.json"
        write_raw_file_atomically(
            catalog_file_path,
            json.dumps(catalog_data, indent=2).encode("utf-8"),
        )
        catalog_sha = compute_sha256(catalog_file_path)
        catalog_rel = str(catalog_file_path.relative_to(workspace_root)).replace("\\", "/")
        manifest.catalog_snapshot_file = catalog_rel
        manifest.files.append(
            ManifestFileEntry(
                relative_path=catalog_rel,
                byte_size=catalog_file_path.stat().st_size,
                sha256=catalog_sha,
                record_count=len(catalog_items),
            )
        )

        # Step 2: Download each selected archive sequentially
        for file_name in config.selected_files:
            file_download_endpoint = config.download_endpoint_template.format(file_name=file_name)
            download_url = f"{config.base_url}{file_download_endpoint}"
            target_path = raw_run_dir / file_name

            logger.info("Downloading %s from %s...", file_name, download_url)

            def fetch_file() -> httpx.Response:
                return client.get(download_url)

            resp = execute_with_retry(fetch_file)
            write_raw_file_atomically(target_path, resp.content)

            file_sha = compute_sha256(target_path)
            file_rel = str(target_path.relative_to(workspace_root)).replace("\\", "/")

            manifest.files.append(
                ManifestFileEntry(
                    relative_path=file_rel,
                    byte_size=target_path.stat().st_size,
                    sha256=file_sha,
                    record_count=None,
                )
            )

            # Politeness delay
            if config.request_delay_seconds > 0:
                time.sleep(config.request_delay_seconds)

        # Mark complete after all files downloaded and hashed
        manifest.run_status = RunStatus.COMPLETE
        manifest_path = manifest.save(workspace_root / storage.manifests_dir)
        logger.info("ClinPGx raw acquisition complete. Manifest saved to %s", manifest_path)
        return manifest, manifest_path

    finally:
        if should_close_client:
            client.close()

