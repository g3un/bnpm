from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .hash import tree_sha256
from .lockfile import LockedPlugin, load_lockfile
from .store import default_home, default_lock_path, plugin_dir_from_lock


@dataclass(frozen=True)
class VerificationResult:
    plugin: LockedPlugin
    path: Path
    expected: str
    actual: str | None
    ok: bool
    message: str


def verify_plugins(lock_path: Path | None = None, home: Path | None = None) -> list[VerificationResult]:
    lock_path = lock_path or default_lock_path()
    home = home or default_home()
    lockfile = load_lockfile(lock_path)
    return [_verify_plugin(plugin, home) for plugin in lockfile.plugins]


def _verify_plugin(plugin: LockedPlugin, home: Path) -> VerificationResult:
    path = plugin_dir_from_lock(home, plugin.name, plugin.source, plugin.commit)
    if not path.exists():
        return VerificationResult(
            plugin=plugin,
            path=path,
            expected=plugin.checksum,
            actual=None,
            ok=False,
            message=f"missing plugin path {path}",
        )

    actual = tree_sha256(path)
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
