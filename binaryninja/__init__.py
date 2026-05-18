from pathlib import Path
import sys
import threading


_ROOT = Path(__file__).resolve().parent

_PACKED_PACKAGE = _ROOT / "bnpm"
if _PACKED_PACKAGE.is_dir() and str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if _PACKED_PACKAGE.is_dir() and "__path__" in globals():
    __path__.append(str(_PACKED_PACKAGE))


try:
    from bnpm.runtime import activate
    from bnpm.sync import sync
    from binaryninja import PluginCommand, log_error, log_info

    _sync_lock = threading.Lock()

    activate()

    def sync_plugins(bv=None):
        thread = threading.Thread(target=_sync_plugins_background, daemon=True)
        thread.start()

    def _sync_plugins_background():
        if not _sync_lock.acquire(blocking=False):
            log_info("sync already running", logger="BNPM")
            return
        try:
            log_info("sync started", logger="BNPM")
            installed = sync(progress=lambda message: log_info(message, logger="BNPM"))
            log_info(f"synced {len(installed)} plugin(s)", logger="BNPM")
            activate()
        except Exception as exc:
            log_error(f"sync failed: {exc}", logger="BNPM")
        finally:
            _sync_lock.release()

    PluginCommand.register("BNPM\\Sync", "Sync BNPM plugins from bnpm.toml", sync_plugins)
except Exception as exc:
    try:
        from binaryninja import log_error

        log_error(f"failed to activate: {exc}", logger="BNPM")
    except Exception:
        raise
