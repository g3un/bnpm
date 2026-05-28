from __future__ import annotations

from pathlib import Path

from ..lockfile import load_lockfile


def run(lock_path: Path) -> int:
    lockfile = load_lockfile(lock_path)
    for plugin in sorted(lockfile.plugins, key=lambda item: item.name):
        print(f"{plugin.name}\t{plugin.version or 'local'}\t{plugin.commit or plugin.source}")
    return 0
