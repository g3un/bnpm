from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import shutil
import sys

from .errors import BnpmError
from .fetch import install
from .lockfile import LockedPlugin, load_lockfile, merge_plugins, write_lockfile
from .manifest import Manifest, load_manifest, write_manifest
from .packages import install_packages, lock_dependencies
from .setup import setup_binaryninja
from .source import SourceSpec, parse_plugin
from .status import load_manifest_plugins, lock_mismatches
from .store import default_home, default_manifest_path, plugin_dir_from_lock
from .sync import resolve_manifest_path_spec, sync
from .verify import verify_plugins


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bnpm")
    parser.add_argument("--manifest-path", default=None)
    parser.add_argument("--home", default=None)

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("name")
    source_group = add_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--git")
    source_group.add_argument("--path")
    ref_group = add_parser.add_mutually_exclusive_group()
    ref_group.add_argument("--tag")
    ref_group.add_argument("--branch")
    ref_group.add_argument("--rev")

    remove_parser = subparsers.add_parser("remove")
    remove_parser.add_argument("name")

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("names", nargs="*")

    subparsers.add_parser("sync")
    subparsers.add_parser("verify")
    subparsers.add_parser("list")
    setup_parser = subparsers.add_parser("setup")
    setup_parser.add_argument("--plugin-dir", default=None)

    args = parser.parse_args(argv)
    manifest_path = Path(args.manifest_path).expanduser().resolve() if args.manifest_path else default_manifest_path()
    lock_path = manifest_path.with_name("bnpm.lock")
    home = Path(args.home).expanduser().resolve() if args.home else default_home()

    try:
        if args.command == "add":
            return _add(
                args.name,
                args.git,
                args.path,
                args.tag,
                args.branch,
                args.rev,
                manifest_path,
                lock_path,
                home,
            )
        if args.command == "remove":
            return _remove(args.name, manifest_path, lock_path, home)
        if args.command == "update":
            return _update(args.names, manifest_path, lock_path, home)
        if args.command == "sync":
            return _sync(manifest_path, lock_path, home)
        if args.command == "verify":
            return _verify(lock_path, home)
        if args.command == "list":
            return _list(lock_path)
        if args.command == "setup":
            return _setup(Path(args.plugin_dir) if args.plugin_dir else None)
    except BnpmError as exc:
        print(f"bnpm: {exc}", file=sys.stderr)
        return 1
    return 0


def _add(
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
    _ensure_clean_manifest_lock(manifest_path, lock_path)
    manifest = _load_or_empty_manifest(manifest_path)

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
    return _sync(manifest_path, lock_path, home)


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


def _remove(name: str, manifest_path: Path, lock_path: Path, home: Path) -> int:
    _ensure_clean_manifest_lock(manifest_path, lock_path)
    manifest = load_manifest(manifest_path)
    if name not in manifest.plugins:
        print(f"bnpm: plugin {name!r} is not in bnpm.toml", file=sys.stderr)
        return 1

    lockfile = load_lockfile(lock_path)
    locked_plugin = next((plugin for plugin in lockfile.plugins if plugin.name == name), None)

    plugins = dict(manifest.plugins)
    del plugins[name]
    write_manifest(manifest_path, plugins)
    code = _sync(manifest_path, lock_path, home)
    if code == 0 and locked_plugin is not None:
        _remove_plugin(locked_plugin, home)
    return code


def _update(names: list[str], manifest_path: Path, lock_path: Path, home: Path) -> int:
    _ensure_clean_manifest_lock(manifest_path, lock_path)
    manifest = load_manifest(manifest_path)
    selected_names = names or list(manifest.plugins)
    missing = sorted(set(selected_names) - set(manifest.plugins))
    if missing:
        print(f"bnpm: unknown plugin(s): {', '.join(missing)}", file=sys.stderr)
        return 1

    installed = [
        install(resolve_manifest_path_spec(manifest.plugins[name], manifest.path.parent), home, progress=_progress)
        for name in selected_names
    ]
    lockfile = load_lockfile(lock_path)
    plugins = merge_plugins(lockfile.plugins, installed)
    packages = install_packages(_requirements(plugins), home, progress=_progress)
    locked_plugins, locked_packages = lock_dependencies(plugins, packages)
    write_lockfile(lock_path, locked_plugins, locked_packages)
    for plugin in installed:
        print(f"updated {plugin.name} {plugin.version or 'local'} {plugin.commit or plugin.source}")
    return 0


def _sync(manifest_path: Path, lock_path: Path, home: Path) -> int:
    installed = sync(manifest_path=manifest_path, lock_path=lock_path, home=home, progress=_progress)
    for plugin in installed:
        print(f"synced {plugin.name} {plugin.version or 'local'} {plugin.commit or plugin.source}")
    return 0


def _list(lock_path: Path) -> int:
    lockfile = load_lockfile(lock_path)
    for plugin in sorted(lockfile.plugins, key=lambda item: item.name):
        print(f"{plugin.name}\t{plugin.version or 'local'}\t{plugin.commit or plugin.source}")
    return 0


def _verify(lock_path: Path, home: Path) -> int:
    results = verify_plugins(lock_path=lock_path, home=home)
    failed = False
    for result in results:
        if result.ok:
            print(f"verified {result.plugin.name} {result.actual}")
        else:
            failed = True
            print(f"bnpm: {result.plugin.name}: {result.message}", file=sys.stderr)
    return 1 if failed else 0


def _setup(plugin_dir: Path | None) -> int:
    target = setup_binaryninja(plugin_dir)
    print(f"installed BNPM Binary Ninja plugin to {target}")
    print("restart Binary Ninja to load BNPM")
    return 0


def _requirements(plugins: list[LockedPlugin]) -> list[str]:
    requirements = []
    for plugin in plugins:
        requirements.extend(plugin.requirements if plugin.requirements is not None else plugin.dependencies or [])
    return requirements


def _progress(message: str) -> None:
    print(f"bnpm: {message}", file=sys.stderr)


def _remove_plugin(plugin: LockedPlugin, home: Path) -> None:
    if plugin.commit is None:
        return
    path = plugin_dir_from_lock(home, plugin.name, plugin.source, plugin.commit)
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
        "bnpm.toml and bnpm.lock differ. Run `bnpm sync` before changing plugins.\n"
        + details
    )


if __name__ == "__main__":
    raise SystemExit(main())
