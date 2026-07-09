from __future__ import annotations

from argparse import ArgumentParser, Namespace
import sys

from ..config import get_config
from ..dependencies import lock_dependencies
from ..fetch import install
from ..lockfile import load_lockfile, merge_plugins, write_lockfile
from ..manifest import load_manifest
from ..packages import install_packages
from ..sync import collect_requirements, resolve_manifest_path_spec
from .common import ensure_clean_manifest_lock, report_progress


def configure_parser(parser: ArgumentParser) -> None:
    parser.add_argument("names", nargs="*")


def run(args: Namespace) -> int:
    config = get_config()
    names = args.names
    manifest_path = config.bnpm_manifest_path
    lock_path = config.bnpm_lock_path
    home = config.bnpm_plugin_dir

    ensure_clean_manifest_lock(manifest_path, lock_path)
    manifest = load_manifest(manifest_path)
    selected_names = names or list(manifest.plugins)
    missing = sorted(set(selected_names) - set(manifest.plugins))
    if missing:
        print(f"bnpm: unknown plugin(s): {', '.join(missing)}", file=sys.stderr)
        return 1

    installed = [
        install(
            resolve_manifest_path_spec(manifest.plugins[name], manifest.path.parent),
            home,
            report_progress=report_progress,
        )
        for name in selected_names
    ]
    lockfile = load_lockfile(lock_path)
    plugins = merge_plugins(lockfile.plugins, installed)
    packages = install_packages(
        collect_requirements(plugins), home, report_progress=report_progress
    )
    locked_plugins, locked_packages = lock_dependencies(plugins, packages)
    write_lockfile(lock_path, locked_plugins, locked_packages)
    for plugin in installed:
        print(
            f"updated {plugin.name} {plugin.version or 'local'} {plugin.commit or plugin.source}"
        )
    return 0
