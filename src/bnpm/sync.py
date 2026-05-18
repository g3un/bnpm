from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .fetch import install
from .lockfile import LockedPlugin, write_lockfile
from .manifest import load_manifest
from .source import SourceSpec
from .store import default_home, default_lock_path, default_manifest_path


def sync(
    manifest_path: Path | None = None,
    lock_path: Path | None = None,
    home: Path | None = None,
) -> list[LockedPlugin]:
    manifest_path = manifest_path or default_manifest_path()
    lock_path = lock_path or default_lock_path()
    home = home or default_home()

    manifest = load_manifest(manifest_path)
    installed = [
        install(resolve_manifest_path_spec(spec, manifest.path.parent), home)
        for spec in manifest.plugins.values()
    ]
    write_lockfile(lock_path, installed)
    return installed


def resolve_manifest_path_spec(spec: SourceSpec, base: Path) -> SourceSpec:
    if spec.kind != "path" or spec.path is None:
        return spec
    path = Path(spec.path).expanduser()
    if path.is_absolute():
        return spec
    return replace(spec, path=str((base / path).resolve()))
