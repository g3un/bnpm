from __future__ import annotations

from pathlib import Path

from ..sync import sync
from .common import report_progress


def run(manifest_path: Path, lock_path: Path, home: Path) -> int:
    installed = sync(manifest_path=manifest_path, lock_path=lock_path, home=home, report_progress=report_progress)
    for plugin in installed:
        print(f"synced {plugin.name} {plugin.version or 'local'} {plugin.commit or plugin.source}")
    return 0



