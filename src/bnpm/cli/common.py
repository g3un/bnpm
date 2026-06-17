from __future__ import annotations

from pathlib import Path
import sys

from ..errors import BnpmError
from ..lockfile import load_lockfile
from ..manifest import load_manifest
from ..models import LockedPlugin, Manifest
from ..status import load_manifest_plugins, collect_lock_mismatches


def report_progress(message: str) -> None:
    print(f"bnpm: {message}", file=sys.stderr)


def collect_requirements(plugins: list[LockedPlugin]) -> list[str]:
    result = []
    for plugin in plugins:
        result.extend(
            plugin.requirements
            if plugin.requirements is not None
            else plugin.dependencies or []
        )
    return result


def load_or_empty_manifest(manifest_path: Path) -> Manifest:
    if manifest_path.exists():
        return load_manifest(manifest_path)
    return Manifest(path=manifest_path, version=1, plugins={})


def ensure_clean_manifest_lock(manifest_path: Path, lock_path: Path) -> None:
    if not manifest_path.exists():
        return
    mismatches = collect_lock_mismatches(
        load_manifest_plugins(manifest_path),
        load_lockfile(lock_path),
    )
    if not mismatches:
        return
    details = "\n".join(f"  - {message}" for message in mismatches)
    raise BnpmError(
        "bnpm.toml and bnpm.lock differ. Run `bnpm sync` before changing plugins.\n"
        + details
    )
