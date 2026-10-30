"""Git utilities to record repository commit in run manifests."""

import subprocess
from pathlib import Path


def get_git_commit_hash(cwd: Path | str | None = None) -> str:
    """Return the current HEAD commit hash, or 'uncommitted' if not yet committed."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "uncommitted"

