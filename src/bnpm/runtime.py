from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

from .hash import tree_sha256
from .lockfile import load_lockfile
from .plugin_types import legacy_python, pyproject
from .status import load_manifest_plugins, lock_mismatches
from .store import default_home, default_lock_path, package_dir, plugin_dir_from_lock
from .sync import sync


LOGGER = "BNPM"


def activate(lock_path: Path | None = None, home: Path | None = None) -> None:
    home = home or default_home()
    lock_path = lock_path or _default_lock_path()
    _log_info(f"activating with lock={lock_path} home={home}")
    lockfile = load_lockfile(lock_path)
    lockfile = _maybe_sync_stale_manifest(lock_path, home, lockfile)
    _log_info(f"found {len(lockfile.plugins)} locked plugin(s)")
    _add_package_dir(home)

    for plugin in lockfile.plugins:
        _log_info(f"resolving {plugin.name} from {plugin.source}")
        plugin_path = _resolve_plugin_path(home, plugin.name, plugin.source, plugin.commit)
        if plugin_path is None:
            continue
        if not _verify_checksum(plugin.name, plugin_path, plugin.commit is None, plugin.checksum):
            continue
        _load_plugin(plugin.name, plugin_path)


def _default_lock_path() -> Path:
    override = os.environ.get("BNPM_LOCK")
    if override:
        return Path(override).expanduser().resolve()
    return default_lock_path()


def _maybe_sync_stale_manifest(lock_path, home, lockfile):
    manifest_path = lock_path.with_name("bnpm.toml")
    try:
        manifest_plugins = load_manifest_plugins(manifest_path)
        mismatches = lock_mismatches(manifest_plugins, lockfile)
    except Exception as exc:
        _log_warning(f"could not compare bnpm.toml and bnpm.lock: {exc}")
        return lockfile

    if not mismatches:
        return lockfile

    _log_warning("bnpm.toml and bnpm.lock differ:")
    for message in mismatches:
        _log_warning(f"  {message}")

    if not _confirm_sync(mismatches):
        _log_info("using existing bnpm.lock")
        return lockfile

    try:
        installed = sync(
            manifest_path=manifest_path,
            lock_path=lock_path,
            home=home,
            progress=_log_info,
        )
        _log_info(f"synced {len(installed)} plugin(s)")
        return load_lockfile(lock_path)
    except Exception as exc:
        _log_error(f"sync failed: {exc}; using existing bnpm.lock")
        return lockfile


def _confirm_sync(mismatches: list[str]) -> bool:
    try:
        import binaryninja

        buttons = getattr(binaryninja.MessageBoxButtonSet, "YesNoButtonSet", None)
        if buttons is None:
            buttons = getattr(binaryninja.MessageBoxButtonSet, "OKCancelButtonSet")
        icon = getattr(binaryninja.MessageBoxIcon, "WarningIcon", 0)
        details = "\n".join(f"- {message}" for message in mismatches[:8])
        if len(mismatches) > 8:
            details += f"\n- ... and {len(mismatches) - 8} more"
        result = binaryninja.show_message_box(
            "BNPM",
            f"bnpm.toml and bnpm.lock differ.\n\n{details}\n\nSync now?",
            buttons,
            icon,
        )
        return _is_positive_message_box_result(
            result,
            getattr(binaryninja, "MessageBoxButtonResult", None),
        )
    except Exception:
        return False


def _is_positive_message_box_result(result, result_type=None) -> bool:
    if result_type is not None:
        yes = getattr(result_type, "YesButton", None)
        ok = getattr(result_type, "OKButton", None)
        if result == yes or result == ok:
            return True
    name = getattr(result, "name", str(result))
    return name in {"YesButton", "OKButton"}


def _resolve_plugin_path(home: Path, name: str, source: str, commit: str | None) -> Path | None:
    try:
        return plugin_dir_from_lock(home, name, source, commit)
    except ValueError as exc:
        _log_warning(f"skipped plugin: {exc}")
        return None


def _add_package_dir(home: Path) -> None:
    path = package_dir(home)
    if not path.exists():
        return
    package_path = str(path)
    if package_path not in sys.path:
        sys.path.insert(0, package_path)


def _verify_checksum(name: str, plugin_path: Path, is_path_plugin: bool, expected: str) -> bool:
    if not plugin_path.exists():
        _log_warning(f"skipped {name}: missing plugin path {plugin_path}")
        return False

    actual = tree_sha256(plugin_path)
    if actual == expected:
        return True

    message = f"checksum mismatch for {name}: expected {expected}, got {actual}"
    if is_path_plugin:
        _log_warning(message)
        return True

    _log_warning(f"{message}; skipping plugin")
    return False


def _load_plugin(name: str, plugin_path: Path) -> None:
    entry = _resolve_plugin_entry(name, plugin_path)
    if entry is None:
        return
    init_path, import_base = entry

    plugin_parent = str(import_base)
    if plugin_parent not in sys.path:
        sys.path.insert(0, plugin_parent)

    module_name = f"_bnpm_plugin_{_sanitize(name)}"
    if module_name in sys.modules:
        _log_info(f"skipped {name}: already loaded as {module_name}")
        return

    spec = importlib.util.spec_from_file_location(
        module_name,
        init_path,
        submodule_search_locations=[str(init_path.parent)],
    )
    if spec is None or spec.loader is None:
        _log_warning(f"skipped {name}: cannot create import spec")
        return

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        _log_info(f"loaded {name} from {plugin_path}")
    except Exception:
        sys.modules.pop(module_name, None)
        _log_error(f"failed to load {name} from {plugin_path}")
        raise


def _sanitize(name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in name)


def _resolve_plugin_entry(name: str, plugin_path: Path) -> tuple[Path, Path] | None:
    pyproject_path = plugin_path / "pyproject.toml"
    if pyproject_path.exists():
        entry = pyproject.resolve_entry(name, plugin_path, _log_warning)
        if entry is not None:
            return entry

    entry = legacy_python.resolve_entry(plugin_path)
    if entry is not None:
        return entry

    _log_warning(f"skipped {name}: missing plugin entry point")
    return None


def _log_warning(message: str) -> None:
    try:
        from binaryninja import log_warn

        log_warn(message, logger=LOGGER)
    except Exception:
        print(f"[BNPM] {message}", file=sys.stderr)


def _log_info(message: str) -> None:
    try:
        from binaryninja import log_info

        log_info(message, logger=LOGGER)
    except Exception:
        print(f"[BNPM] {message}", file=sys.stderr)


def _log_error(message: str) -> None:
    try:
        from binaryninja import log_error

        log_error(message, logger=LOGGER)
    except Exception:
        print(f"[BNPM] {message}", file=sys.stderr)
