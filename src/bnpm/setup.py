from __future__ import annotations

import os
import platform
from pathlib import Path

from .bundle import build_bundle
from .errors import BnpmError


def setup_binaryninja(plugin_dir: Path | None = None) -> Path:
    plugin_dir = plugin_dir.expanduser().resolve() if plugin_dir else default_binaryninja_plugin_dir()
    target = plugin_dir / "bnpm"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    return build_bundle(target)


def default_binaryninja_plugin_dir() -> Path:
    override = os.environ.get("BNPM_BINARYNINJA_PLUGIN_DIR")
    if override:
        return Path(override).expanduser().resolve()

    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Binary Ninja" / "plugins"
    if system == "Windows":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "Binary Ninja" / "plugins"
        raise BnpmError("APPDATA is not set; pass --plugin-dir")
    return Path.home() / ".binaryninja" / "plugins"
