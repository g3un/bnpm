from __future__ import annotations

import sys


LOGGER = "BNPM"


def log_warning(message: str) -> None:
    try:
        from binaryninja import log_warn

        log_warn(message, logger=LOGGER)
    except Exception:
        print(f"[BNPM] {message}", file=sys.stderr)


def log_info(message: str) -> None:
    try:
        from binaryninja import log_info

        log_info(message, logger=LOGGER)
    except Exception:
        print(f"[BNPM] {message}", file=sys.stderr)


def log_error(message: str) -> None:
    try:
        from binaryninja import log_error

        log_error(message, logger=LOGGER)
    except Exception:
        print(f"[BNPM] {message}", file=sys.stderr)
