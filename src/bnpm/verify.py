from __future__ import annotations

from pathlib import Path

from .config import get_config
from .utils.hash import compute_tree_sha256
from .lockfile import load_lockfile
from .models import LockedPlugin, VerificationResult
from .utils.locations import resolve_plugin_dir_from_lock


def verify_plugins(lock_path: Path | None = None, home: Path | None = None) -> list[VerificationResult]:
    config = get_config()
    lock_path = lock_path or config.bnpm_lock_path
    home = home or config.bnpm_plugin_dir
    lockfile = load_lockfile(lock_path)
    return [_verify_plugin(plugin, home) for plugin in lockfile.plugins]


def _verify_plugin(plugin: LockedPlugin, home: Path) -> VerificationResult:
    path = resolve_plugin_dir_from_lock(home, plugin.name, plugin.source, plugin.commit)
    if not path.exists():
        return VerificationResult(
            plugin=plugin,
            path=path,
            expected=plugin.checksum,
            actual=None,
            ok=False,
            message=f"missing plugin path {path}",
        )

    actual = compute_tree_sha256(path)
    if actual == plugin.checksum:
        return VerificationResult(
            plugin=plugin,
            path=path,
            expected=plugin.checksum,
            actual=actual,
            ok=True,
            message="ok",
        )

    return VerificationResult(
        plugin=plugin,
        path=path,
        expected=plugin.checksum,
        actual=actual,
        ok=False,
        message=f"checksum mismatch: expected {plugin.checksum}, got {actual}",
    )



