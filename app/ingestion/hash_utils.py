"""Cryptographic hashing and raw file immutability utilities.

Adheres strictly to Phase 1 rules:
- Raw files are write-once; refuses to overwrite existing files
- Binary mode for all hashing and raw writes
- Write to temp file in same directory and atomic rename with os.replace
"""

import hashlib
import os
from pathlib import Path


def compute_sha256(file_path: Path | str, chunk_size: int = 65536) -> str:
    """Compute the hex-encoded SHA-256 hash of a file in binary mode."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for hashing: {path}")
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_raw_file_atomically(
    destination_path: Path | str,
    content: bytes,
    allow_overwrite: bool = False,
) -> Path:
    """Write raw content to destination atomically using a temp file and os.replace.
    
    Enforces raw immutability: raises FileExistsError if allow_overwrite is False
    and destination file already exists.
    """
    dest = Path(destination_path)
    if not allow_overwrite and dest.exists():
        raise FileExistsError(
            f"Raw immutability violation: file already exists and cannot be overwritten: {dest.resolve()}"
        )
    
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest.parent / f"{dest.name}.tmp_{os.getpid()}"
    
    try:
        with temp_path.open("wb") as f:
            f.write(content)
        # os.replace is atomic on both POSIX and Windows (Python 3.3+)
        os.replace(temp_path, dest)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

    return dest

