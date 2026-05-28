from __future__ import annotations

from pathlib import Path
import shutil
import sys

from ..lockfile import load_lockfile
from ..manifest import load_manifest, write_manifest
from ..models import LockedPlugin
from ..utils.locations import resolve_plugin_dir_from_lock
from .common import ensure_clean_manifest_lock
from .sync import run as sync_run


def run(name: str, manifest_path: Path, lock_path: Path, home: Path) -> int:
    ensure_clean_manifest_lock(manifest_path, lock_path)
    manifest = load_manifest(manifest_path)
    if name not in manifest.plugins:
        print(f"bnpm: plugin {name!r} is not in bnpm.toml", file=sys.stderr)
        return 1

    lockfile = load_lockfile(lock_path)
    locked_plugin = next((plugin for plugin in lockfile.plugins if plugin.name == name), None)

    plugins = dict(manifest.plugins)
    del plugins[name]
    write_manifest(manifest_path, plugins)
    code = sync_run(manifest_path, lock_path, home)
    if code == 0 and locked_plugin is not None:
        _remove_plugin(locked_plugin, home)
    return code


def _remove_plugin(plugin: LockedPlugin, home: Path) -> None:
    if plugin.commit is None:
        return
    path = resolve_plugin_dir_from_lock(home, plugin.name, plugin.source, plugin.commit)
    home = home.resolve()
    if not path.exists() or not path.is_relative_to(home):
        return
    shutil.rmtree(path)
    _remove_empty_parents(path.parent, home)


def _remove_empty_parents(path: Path, stop: Path) -> None:
    path = path.resolve()
    stop = stop.resolve()
    while path != stop and path.is_relative_to(stop):
        try:
            path.rmdir()
        except OSError:
            return
        path = path.parent


