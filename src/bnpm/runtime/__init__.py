from __future__ import annotations

from pathlib import Path

from ..config import get_config
from ..lockfile import load_lockfile
from ..utils.locations import resolve_package_dir
from .loader import load_plugin, resolve_plugin_path, verify_install
from .logs import log_info
from .python import build_plugin_python_env, resolve_plugin_python_executable, spawn_plugin_python
from .sync import sync_stale_manifest_if_needed


def activate(lock_path: Path | None = None, home: Path | None = None) -> None:
    config = get_config()
    home = home or config.bnpm_plugin_dir
    lock_path = lock_path or config.bnpm_lock_path
    log_info(f"activating with lock={lock_path} home={home}")
    lockfile = load_lockfile(lock_path)
    lockfile = sync_stale_manifest_if_needed(lock_path, home, lockfile)
    log_info(f"found {len(lockfile.plugins)} locked plugin(s)")
    _add_package_dir(home)

    for plugin in lockfile.plugins:
        log_info(f"resolving {plugin.name} from {plugin.source}")
        plugin_path = resolve_plugin_path(home, plugin)
        if plugin_path is None:
            continue
        if not verify_install(plugin, plugin_path):
            continue
        load_plugin(plugin.name, plugin_path)


def _add_package_dir(home: Path) -> None:
    import site
    import sys

    path = resolve_package_dir(home)
    if not path.exists():
        return
    package_path = str(path)
    site.addsitedir(package_path)
    if package_path in sys.path:
        sys.path.remove(package_path)
    sys.path.insert(0, package_path)


__all__ = [
    "activate",
    "build_plugin_python_env",
    "resolve_plugin_python_executable",
    "spawn_plugin_python",
]




