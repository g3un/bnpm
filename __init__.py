from pathlib import Path
import sys


_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_SRC_PACKAGE = _SRC / "bnpm"
if _SRC_PACKAGE.is_dir() and "__path__" in globals():
    __path__.append(str(_SRC_PACKAGE))


try:
    from bnpm.runtime import activate
    from bnpm.sync import sync
    from binaryninja import PluginCommand, log_error, log_info

    activate()

    def sync_plugins(bv=None):
        try:
            installed = sync()
            log_info(f"synced {len(installed)} plugin(s)", logger="BNPM")
            activate()
        except Exception as exc:
            log_error(f"sync failed: {exc}", logger="BNPM")

    PluginCommand.register("BNPM\\Sync", "Sync BNPM plugins from bnpm.toml", sync_plugins)
except Exception as exc:
    try:
        from binaryninja import log_error

        log_error(f"failed to activate: {exc}", logger="BNPM")
    except Exception:
        raise
