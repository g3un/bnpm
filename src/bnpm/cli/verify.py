from __future__ import annotations

from pathlib import Path
import sys

from ..verify import verify_plugins


def run(lock_path: Path, home: Path) -> int:
    results = verify_plugins(lock_path=lock_path, home=home)
    failed = False
    for result in results:
        if result.ok:
            print(f"verified {result.plugin.name} {result.actual}")
        else:
            failed = True
            print(f"bnpm: {result.plugin.name}: {result.message}", file=sys.stderr)
    return 1 if failed else 0
