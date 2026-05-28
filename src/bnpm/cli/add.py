from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ..errors import BnpmError
from ..manifest import write_manifest
from ..models import SourceSpec
from ..source import parse_plugin
from .common import ensure_clean_manifest_lock, load_or_empty_manifest
from .sync import run as sync_run


def run(
    name: str,
    git: str | None,
    path: str | None,
    tag: str | None,
    branch: str | None,
    rev: str | None,
    manifest_path: Path,
    lock_path: Path,
    home: Path,
) -> int:
    ensure_clean_manifest_lock(manifest_path, lock_path)
    manifest = load_or_empty_manifest(manifest_path)

    if path is not None:
        if tag or branch or rev:
            raise BnpmError("local path plugins cannot set tag, branch, or rev")
        source_path = Path(path).expanduser()
        spec = parse_plugin(name, {"path": str(source_path.resolve())})
    else:
        assert git is not None
        spec = parse_plugin(name, git)
        spec = _apply_ref_options(spec, tag=tag, branch=branch, rev=rev)

    plugins = dict(manifest.plugins)
    plugins[name] = spec
    write_manifest(manifest_path, plugins)
    return sync_run(manifest_path, lock_path, home)


def _apply_ref_options(
    spec: SourceSpec,
    *,
    tag: str | None,
    branch: str | None,
    rev: str | None,
) -> SourceSpec:
    if not any((tag, branch, rev)):
        return spec
    if spec.kind == "path":
        raise BnpmError("local path plugins cannot set tag, branch, or rev")
    if spec.tag or spec.branch or spec.rev:
        raise BnpmError("plugin source already specifies a ref")
    return replace(spec, tag=tag, branch=branch, rev=rev)
