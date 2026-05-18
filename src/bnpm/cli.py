from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .errors import BnpmError
from .fetch import install
from .lockfile import load_lockfile, merge_plugins, write_lockfile
from .manifest import load_manifest
from .source import parse_plugin
from .store import default_home, default_manifest_path
from .sync import resolve_manifest_path_spec, sync


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bnpm")
    parser.add_argument("--manifest-path", default=None)
    parser.add_argument("--home", default=None)

    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("plugin", nargs="?")

    subparsers.add_parser("sync")
    subparsers.add_parser("list")

    args = parser.parse_args(argv)
    manifest_path = Path(args.manifest_path).expanduser().resolve() if args.manifest_path else default_manifest_path()
    lock_path = manifest_path.with_name("bnpm.lock")
    home = Path(args.home).expanduser().resolve() if args.home else default_home()

    try:
        if args.command == "install":
            return _install(args.plugin, manifest_path, lock_path, home)
        if args.command == "sync":
            return _sync(manifest_path, lock_path, home)
        if args.command == "list":
            return _list(lock_path)
    except BnpmError as exc:
        print(f"bnpm: {exc}", file=sys.stderr)
        return 1
    return 0


def _install(plugin: str | None, manifest_path: Path, lock_path: Path, home: Path) -> int:
    if plugin:
        name = _name_from_plugin(plugin)
        specs = [parse_plugin(name, plugin)]
    else:
        manifest = load_manifest(manifest_path)
        specs = [
            resolve_manifest_path_spec(spec, manifest.path.parent)
            for spec in manifest.plugins.values()
        ]

    installed = [install(spec, home) for spec in specs]
    lockfile = load_lockfile(lock_path)
    write_lockfile(lock_path, merge_plugins(lockfile.plugins, installed))
    for plugin in installed:
        print(f"installed {plugin.name} {plugin.version or 'local'} {plugin.commit or plugin.source}")
    return 0


def _sync(manifest_path: Path, lock_path: Path, home: Path) -> int:
    installed = sync(manifest_path=manifest_path, lock_path=lock_path, home=home)
    for plugin in installed:
        print(f"synced {plugin.name} {plugin.version or 'local'} {plugin.commit or plugin.source}")
    return 0


def _list(lock_path: Path) -> int:
    lockfile = load_lockfile(lock_path)
    for plugin in sorted(lockfile.plugins, key=lambda item: item.name):
        print(f"{plugin.name}\t{plugin.version or 'local'}\t{plugin.commit or plugin.source}")
    return 0


def _name_from_plugin(value: str) -> str:
    source = value.split("@", 1)[0].split("?", 1)[0].removesuffix(".git").rstrip("/")
    return source.rsplit("/", 1)[-1].replace("-", "_")


if __name__ == "__main__":
    raise SystemExit(main())
