"""Tests for raw immutability enforcement."""

import hashlib
import pytest
from app.ingestion.hash_utils import compute_sha256, write_raw_file_atomically


def test_write_raw_file_atomically_success(tmp_path):
    target_file = tmp_path / "raw_data.bin"
    content = b"original raw byte stream"

    written_path = write_raw_file_atomically(target_file, content)
    assert written_path.is_file()
    assert written_path.read_bytes() == content
    assert compute_sha256(written_path) == hashlib.sha256(content).hexdigest()


def test_write_raw_file_immutability_violation(tmp_path):
    target_file = tmp_path / "immutable.bin"
    target_file.write_bytes(b"initial data")

    # Attempting to overwrite existing raw file must raise FileExistsError
    with pytest.raises(FileExistsError) as exc_info:
        write_raw_file_atomically(target_file, b"new data", allow_overwrite=False)

    assert "Raw immutability violation" in str(exc_info.value)
    # File content remains unchanged
    assert target_file.read_bytes() == b"initial data"

