"""Tests for manifest creation, validation, and hash verification."""

import json
from pathlib import Path
import pytest

from app.config.manifest import BaseRunManifest, ManifestFileEntry, RunStatus
from app.ingestion.hash_utils import compute_sha256
from app.ingestion.verify import verify_manifest


def test_manifest_validation_and_verify_pass(tmp_path):
    # Setup mock files
    raw_dir = tmp_path / "raw" / "source1" / "run_001"
    raw_dir.mkdir(parents=True)
    file1 = raw_dir / "data1.bin"
    file1.write_bytes(b"content for file 1")
    sha1 = compute_sha256(file1)

    manifests_dir = tmp_path / "manifests"

    manifest = BaseRunManifest(
        run_id="run_001",
        source_name="Source1",
        endpoint_url="https://api.source1.org",
        retrieval_timestamp_utc="2026-10-30T12:00:00Z",
        source_version="2026-10",
        license_name="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        license_checked_date="2026-10-30",
        git_commit="abc1234",
        run_status=RunStatus.COMPLETE,
        files=[
            ManifestFileEntry(
                relative_path=str(file1.relative_to(tmp_path)).replace("\\", "/"),
                byte_size=file1.stat().st_size,
                sha256=sha1,
                record_count=10,
            )
        ],
    )

    manifest_path = manifest.save(manifests_dir)
    assert manifest_path.is_file()

    # Run verification
    report = verify_manifest(manifest_path, workspace_root=tmp_path)
    assert report.is_valid is True
    assert report.total_files_checked == 1
    assert len(report.mismatched_hashes) == 0
    assert len(report.missing_files) == 0
    assert len(report.unexpected_files) == 0


def test_verify_detects_tampered_file(tmp_path):
    raw_dir = tmp_path / "raw" / "source1" / "run_002"
    raw_dir.mkdir(parents=True)
    file1 = raw_dir / "data.bin"
    file1.write_bytes(b"original content")
    sha1 = compute_sha256(file1)

    manifest = BaseRunManifest(
        run_id="run_002",
        source_name="Source1",
        endpoint_url="https://api.source1.org",
        retrieval_timestamp_utc="2026-10-30T12:00:00Z",
        source_version="2026-10",
        license_name="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        license_checked_date="2026-10-30",
        git_commit="abc1234",
        run_status=RunStatus.COMPLETE,
        files=[
            ManifestFileEntry(
                relative_path=str(file1.relative_to(tmp_path)).replace("\\", "/"),
                byte_size=file1.stat().st_size,
                sha256=sha1,
            )
        ],
    )
    manifest_path = manifest.save(tmp_path / "manifests")

    # TAMPER: alter file contents
    file1.write_bytes(b"tampered altered content")

    report = verify_manifest(manifest_path, workspace_root=tmp_path)
    assert report.is_valid is False
    assert len(report.mismatched_hashes) == 1
    assert report.mismatched_hashes[0]["file"] == str(file1.relative_to(tmp_path)).replace("\\", "/")


def test_verify_detects_missing_and_unexpected_files(tmp_path):
    raw_dir = tmp_path / "raw" / "source1" / "run_003"
    raw_dir.mkdir(parents=True)
    file1 = raw_dir / "file1.bin"
    file1.write_bytes(b"content 1")
    sha1 = compute_sha256(file1)

    # An extra unrecorded file in the run directory
    extra_file = raw_dir / "untracked_extra.bin"
    extra_file.write_bytes(b"untracked bytes")

    manifest = BaseRunManifest(
        run_id="run_003",
        source_name="Source1",
        endpoint_url="https://api.source1.org",
        retrieval_timestamp_utc="2026-10-30T12:00:00Z",
        source_version="not provided",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        license_checked_date="2026-10-30",
        git_commit="abc1234",
        run_status=RunStatus.COMPLETE,
        files=[
            ManifestFileEntry(
                relative_path=str(file1.relative_to(tmp_path)).replace("\\", "/"),
                byte_size=file1.stat().st_size,
                sha256=sha1,
            ),
            ManifestFileEntry(
                relative_path="raw/source1/run_003/deleted_file.bin",
                byte_size=100,
                sha256="0" * 64,
            ),
        ],
    )
    manifest_path = manifest.save(tmp_path / "manifests")

    report = verify_manifest(manifest_path, workspace_root=tmp_path)
    assert report.is_valid is False
    assert "raw/source1/run_003/deleted_file.bin" in report.missing_files
    assert any("untracked_extra.bin" in uf for uf in report.unexpected_files)

