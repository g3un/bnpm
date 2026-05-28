from __future__ import annotations

from pathlib import Path

from ..lockfile import load_lockfile
from ..models import Lockfile
from ..status import load_manifest_plugins, collect_lock_mismatches
from ..sync import sync
from .logs import log_error, log_info, log_warning


def sync_stale_manifest_if_needed(lock_path: Path, home: Path, lockfile: Lockfile) -> Lockfile:
    manifest_path = lock_path.with_name("bnpm.toml")
    try:
        collect_manifest_plugins = load_manifest_plugins(manifest_path)
        mismatches = collect_lock_mismatches(collect_manifest_plugins, lockfile)
    except Exception as exc:
        log_warning(f"could not compare bnpm.toml and bnpm.lock: {exc}")
        return lockfile

    if not mismatches:
        return lockfile

    log_warning("bnpm.toml and bnpm.lock differ:")
    for message in mismatches:
        log_warning(f"  {message}")

    if not _confirm_sync(mismatches):
        log_info("using existing bnpm.lock")
        return lockfile

    try:
        installed = sync(
            manifest_path=manifest_path,
            lock_path=lock_path,
            home=home,
            report_progress=log_info,
        )
        log_info(f"synced {len(installed)} plugin(s)")
        return load_lockfile(lock_path)
    except Exception as exc:
        log_error(f"sync failed: {exc}; using existing bnpm.lock")
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





