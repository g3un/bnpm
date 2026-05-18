from __future__ import annotations

import hashlib
from pathlib import Path


IGNORED_DIRS = {".git", "__pycache__", ".venv", "venv"}


def tree_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        rel = item.relative_to(path)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        if item.is_dir():
            continue
        digest.update(rel.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()
