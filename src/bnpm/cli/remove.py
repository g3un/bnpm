from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path
import shutil
import sys

from ..config import get_config
from ..lockfile import load_lockfile
from ..manifest import load_manifest, write_manifest
from ..models import LockedPlugin
from ..utils.locations import resolve_plugin_dir_from_lock
from .command import Command
from .common import ensure_clean_manifest_lock
from .sync import sync_plugins


class RemoveCommand(Command):
    name = "remove"

    @classmethod
    def configure_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument("names", nargs="+")

    @classmethod
    def run(cls, args: Namespace) -> int:
        config = get_config()
        names = list(dict.fromkeys(args.names))
        manifest_path = config.bnpm_manifest_path
        lock_path = config.bnpm_lock_path
        home = config.bnpm_plugin_dir

        ensure_clean_manifest_lock(manifest_path, lock_path)
        manifest = load_manifest(manifest_path)
        missing = sorted(set(names) - set(manifest.plugins))
        if missing:
            quoted = ", ".join(repr(name) for name in missing)
            print(f"bnpm: plugin(s) {quoted} are not in bnpm.toml", file=sys.stderr)
            return 1

        lockfile = load_lockfile(lock_path)
        locked_plugins = [plugin for plugin in lockfile.plugins if plugin.name in names]

        plugins = dict(manifest.plugins)
        for name in names:
            del plugins[name]
        write_manifest(manifest_path, plugins)
        code = sync_plugins(manifest_path, lock_path, home)
        if code == 0:
            for plugin in locked_plugins:
                _remove_plugin(plugin, home)
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


