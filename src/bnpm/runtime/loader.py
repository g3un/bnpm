from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from ..installed import does_installed_match_lock, read_installed_plugin
from ..models import InstalledPlugin, LockedPlugin
from ..plugin_types import legacy_python, pyproject
from ..utils.locations import resolve_plugin_dir_from_lock
from .logs import log_error, log_info, log_warning


def resolve_plugin_path(home: Path, plugin: LockedPlugin) -> Path | None:
    try:
        return resolve_plugin_dir_from_lock(
            home, plugin.name, plugin.source, plugin.commit
        )
    except ValueError as exc:
        log_warning(f"skipped plugin: {exc}")
        return None


def verify_install(plugin: LockedPlugin, plugin_path: Path) -> bool:
    if not plugin_path.exists():
        log_warning(f"skipped {plugin.name}: missing plugin path {plugin_path}")
        return False

    if plugin.commit is None:
        return True

    installed = _read_install_metadata(plugin.name, plugin_path)
    if installed is not None and does_installed_match_lock(installed, plugin):
        return True

    log_warning(f"skipped {plugin.name}: install metadata does not match bnpm.lock")
    return False


def load_plugin(name: str, plugin_path: Path) -> None:
    entry = resolve_plugin_entry(name, plugin_path)
    if entry is None:
        return
    init_path, import_base = entry

    plugin_parent = str(import_base)
    if plugin_parent not in sys.path:
        sys.path.insert(0, plugin_parent)

    module_name = f"_bnpm_plugin_{_sanitize_name(name)}"
    if module_name in sys.modules:
        log_info(f"skipped {name}: already loaded as {module_name}")
        return

    spec = importlib.util.spec_from_file_location(
        module_name,
        init_path,
        submodule_search_locations=[str(init_path.parent)],
    )
    if spec is None or spec.loader is None:
        log_warning(f"skipped {name}: cannot create import spec")
        return

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        log_info(f"loaded {name} from {plugin_path}")
    except Exception:
        sys.modules.pop(module_name, None)
        log_error(f"failed to load {name} from {plugin_path}")
        raise


def resolve_plugin_entry(name: str, plugin_path: Path) -> tuple[Path, Path] | None:
    pyproject_path = plugin_path / "pyproject.toml"
    if pyproject_path.exists():
        entry = pyproject.resolve_entry(name, plugin_path, log_warning)
        if entry is not None:
            return entry

    entry = legacy_python.resolve_entry(plugin_path)
    if entry is not None:
        return entry

    log_warning(f"skipped {name}: missing plugin entry point")
    return None


def resolve_plugin_path_or_raise(home: Path, plugin: LockedPlugin) -> Path:
    try:
        return resolve_plugin_dir_from_lock(
            home, plugin.name, plugin.source, plugin.commit
        )
    except ValueError as exc:
        from ..errors import BnpmError

        raise BnpmError(str(exc)) from exc


def _read_install_metadata(name: str, plugin_path: Path) -> InstalledPlugin | None:
    try:
        return read_installed_plugin(plugin_path)
    except Exception as exc:
        log_warning(f"{name}: invalid install metadata: {exc}")
        return None


def _sanitize_name(name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in name)
