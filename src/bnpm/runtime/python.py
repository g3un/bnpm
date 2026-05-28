from __future__ import annotations

import os
from pathlib import Path
import subprocess

from ..config import get_config
from ..errors import BnpmError
from ..lockfile import load_lockfile
from ..models import Lockfile
from ..utils.locations import resolve_package_dir
from .loader import resolve_plugin_path_or_raise, resolve_plugin_entry, verify_install


def resolve_plugin_python_executable() -> Path:
    python = get_config().bnpm_venv_python
    if not python.exists():
        raise BnpmError("BNPM Python environment is missing; run `bnpm setup`")
    return python


def build_plugin_python_env(
    name: str,
    *,
    lock_path: Path | None = None,
    home: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, str]:
    config = get_config()
    home = home or config.bnpm_plugin_dir
    lock_path = lock_path or config.bnpm_lock_path
    lockfile = load_lockfile(lock_path)
    plugin = _find_locked_plugin(lockfile, name)
    plugin_path = resolve_plugin_path_or_raise(home, plugin)
    if not verify_install(plugin, plugin_path):
        raise BnpmError(f"{name}: installed plugin does not match bnpm.lock")

    entry = resolve_plugin_entry(name, plugin_path)
    if entry is None:
        raise BnpmError(f"{name}: missing plugin entry point")
    _, import_base = entry

    result = dict(os.environ if env is None else env)
    result["PYTHONPATH"] = _join_pythonpath(_collect_plugin_pythonpath_entries(home, import_base), result.get("PYTHONPATH"))
    return result


def spawn_plugin_python(
    name: str,
    args: list[str],
    *,
    lock_path: Path | None = None,
    home: Path | None = None,
    env: dict[str, str] | None = None,
    **kwargs,
) -> subprocess.Popen:
    return subprocess.Popen(
        [str(resolve_plugin_python_executable()), *args],
        env=build_plugin_python_env(name, lock_path=lock_path, home=home, env=env),
        **kwargs,
    )


def _find_locked_plugin(lockfile: Lockfile, name: str):
    for plugin in lockfile.plugins:
        if plugin.name == name:
            return plugin
    raise BnpmError(f"{name}: plugin is not in bnpm.lock")


def _collect_plugin_pythonpath_entries(home: Path, import_base: Path) -> list[Path]:
    entries = [import_base]
    packages = resolve_package_dir(home)
    if packages.exists():
        entries.append(packages)
    entries.append(Path(__file__).resolve().parents[2])
    return entries


def _join_pythonpath(entries: list[Path], existing: str | None) -> str:
    values = [str(path) for path in entries]
    if existing:
        values.append(existing)
    return os.pathsep.join(values)



