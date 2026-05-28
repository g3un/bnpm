from __future__ import annotations

from pathlib import Path
import sys

from ..fetch import install
from ..dependencies import lock_dependencies
from ..lockfile import load_lockfile, merge_plugins, write_lockfile
from ..manifest import load_manifest
from ..packages import install_packages
from ..sync import resolve_manifest_path_spec
from .common import ensure_clean_manifest_lock, report_progress, collect_requirements


def run(names: list[str], manifest_path: Path, lock_path: Path, home: Path) -> int:
    ensure_clean_manifest_lock(manifest_path, lock_path)
    manifest = load_manifest(manifest_path)
    selected_names = names or list(manifest.plugins)
    missing = sorted(set(selected_names) - set(manifest.plugins))
    if missing:
        print(f"bnpm: unknown plugin(s): {', '.join(missing)}", file=sys.stderr)
        return 1

    installed = [
        install(resolve_manifest_path_spec(manifest.plugins[name], manifest.path.parent), home, report_progress=report_progress)
        for name in selected_names
    ]
    lockfile = load_lockfile(lock_path)
    plugins = merge_plugins(lockfile.plugins, installed)
    packages = install_packages(collect_requirements(plugins), home, report_progress=report_progress)
    locked_plugins, locked_packages = lock_dependencies(plugins, packages)
    write_lockfile(lock_path, locked_plugins, locked_packages)
    for plugin in installed:
        print(f"updated {plugin.name} {plugin.version or 'local'} {plugin.commit or plugin.source}")
    return 0




