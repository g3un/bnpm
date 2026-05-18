from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .errors import BnpmError
from .lockfile import load_lockfile
from .manifest import Manifest, load_manifest, write_manifest
from .source import parse_plugin
from .status import load_manifest_plugins, lock_mismatches
from .store import default_home, default_manifest_path
from .sync import sync


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bnpm")
    parser.add_argument("--manifest-path", default=None)
    parser.add_argument("--home", default=None)

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("name")
    add_parser.add_argument("source")

    remove_parser = subparsers.add_parser("remove")
    remove_parser.add_argument("name")

    subparsers.add_parser("sync")
    subparsers.add_parser("list")

    args = parser.parse_args(argv)
    manifest_path = Path(args.manifest_path).expanduser().resolve() if args.manifest_path else default_manifest_path()
    lock_path = manifest_path.with_name("bnpm.lock")
    home = Path(args.home).expanduser().resolve() if args.home else default_home()

    try:
        if args.command == "add":
            return _add(args.name, args.source, manifest_path, lock_path, home)
        if args.command == "remove":
            return _remove(args.name, manifest_path, lock_path, home)
        if args.command == "sync":
            return _sync(manifest_path, lock_path, home)
        if args.command == "list":
            return _list(lock_path)
    except BnpmError as exc:
        print(f"bnpm: {exc}", file=sys.stderr)
        return 1
    return 0


def _add(
    name: str,
    source: str,
    manifest_path: Path,
    lock_path: Path,
    home: Path,
) -> int:
    _ensure_clean_manifest_lock(manifest_path, lock_path)
    manifest = _load_or_empty_manifest(manifest_path)

    source_path = Path(source).expanduser()
    if source_path.exists():
        spec = parse_plugin(name, {"path": str(source_path.resolve())})
    else:
        spec = parse_plugin(name, source)

    plugins = dict(manifest.plugins)
    plugins[name] = spec
    write_manifest(manifest_path, plugins)
    return _sync(manifest_path, lock_path, home)


def _remove(name: str, manifest_path: Path, lock_path: Path, home: Path) -> int:
    _ensure_clean_manifest_lock(manifest_path, lock_path)
    manifest = load_manifest(manifest_path)
    if name not in manifest.plugins:
        print(f"bnpm: plugin {name!r} is not in bnpm.toml", file=sys.stderr)
        return 1

    plugins = dict(manifest.plugins)
    del plugins[name]
    write_manifest(manifest_path, plugins)
    return _sync(manifest_path, lock_path, home)


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


def _load_or_empty_manifest(manifest_path: Path) -> Manifest:
    if manifest_path.exists():
        return load_manifest(manifest_path)
    return Manifest(path=manifest_path, version=1, plugins={})


def _ensure_clean_manifest_lock(manifest_path: Path, lock_path: Path) -> None:
    if not manifest_path.exists():
        return
    mismatches = lock_mismatches(
        load_manifest_plugins(manifest_path),
        load_lockfile(lock_path),
    )
    if not mismatches:
        return
    details = "\n".join(f"  - {message}" for message in mismatches)
    raise BnpmError(
        "bnpm.toml and bnpm.lock differ. Run `bnpm sync` before add/remove.\n"
        + details
    )


if __name__ == "__main__":
    raise SystemExit(main())
