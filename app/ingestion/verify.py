"""Verification utility for PharmaGraph raw data manifests.

Recomputes every file hash in a manifest and checks:
- Hash mismatch
- File size mismatch
- Missing files
- Unexpected extra files in the raw run directory
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from app.ingestion.hash_utils import compute_sha256

logger = logging.getLogger(__name__)


@dataclass
class VerificationReport:
    manifest_path: str
    run_id: str
    source_name: str
    total_files_checked: int = 0
    valid_files: list[str] = field(default_factory=list)
    mismatched_hashes: list[dict[str, str]] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    unexpected_files: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return (
            len(self.mismatched_hashes) == 0
            and len(self.missing_files) == 0
            and len(self.unexpected_files) == 0
            and self.total_files_checked > 0
        )


def verify_manifest(
    manifest_path: Path | str,
    workspace_root: Path = Path("."),
) -> VerificationReport:
    """Verify integrity of all files listed in a run manifest."""
    m_path = Path(manifest_path)
    if not m_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {m_path.resolve()}")

    with m_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    run_id = data.get("run_id", "unknown")
    source_name = data.get("source_name", "unknown")
    files_entries = data.get("files", [])

    report = VerificationReport(
        manifest_path=str(m_path).replace("\\", "/"),
        run_id=run_id,
        source_name=source_name,
        total_files_checked=len(files_entries),
    )

    manifest_file_paths = set()
    run_directories = set()

    for entry in files_entries:
        rel_path = entry.get("relative_path")
        expected_sha = entry.get("sha256")
        expected_size = entry.get("byte_size")

        file_path = workspace_root / rel_path
        manifest_file_paths.add(file_path.resolve())
        run_directories.add(file_path.parent)

        if not file_path.is_file():
            report.missing_files.append(rel_path)
            continue

        actual_size = file_path.stat().st_size
        actual_sha = compute_sha256(file_path)

        if actual_sha.lower() != expected_sha.lower() or actual_size != expected_size:
            report.mismatched_hashes.append({
                "file": rel_path,
                "expected_sha": expected_sha,
                "actual_sha": actual_sha,
                "expected_size": expected_size,
                "actual_size": actual_size,
            })
        else:
            report.valid_files.append(rel_path)

    # Check for unexpected extra files in the run directory
    for run_dir in run_directories:
        if run_dir.is_dir():
            for child in run_dir.iterdir():
                if child.is_file() and not child.name.endswith(".tmp"):
                    if child.resolve() not in manifest_file_paths:
                        extra_rel = str(child.relative_to(workspace_root)).replace("\\", "/")
                        report.unexpected_files.append(extra_rel)

    return report

