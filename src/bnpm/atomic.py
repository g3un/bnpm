from __future__ import annotations

import os
from pathlib import Path
import tempfile


def atomic_write_text(path: Path, content: str, *, allow_direct_fallback: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(temp_path, path)
        except PermissionError:
            if not allow_direct_fallback:
                raise
            path.write_text(content, encoding="utf-8", newline="")
            temp_path.unlink(missing_ok=True)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
