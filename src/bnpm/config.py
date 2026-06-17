from __future__ import annotations

from functools import cache
import os
import platform
from pathlib import Path

from .errors import BnpmError
from .helpers import find_bn_install_path
from .models import Config


@cache
def get_config() -> Config:
    return Config(
        bnpm_config_dir=_resolve_default_bnpm_config_dir(),
        bnpm_data_dir=_resolve_default_bnpm_data_dir(),
        bn_install_dir=find_bn_install_path(),
        bn_user_dir=_resolve_default_bn_user_dir(),
    )


def _resolve_default_bnpm_config_dir() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "bnpm"
    return Path.home() / ".config" / "bnpm"


def _resolve_default_bnpm_data_dir() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "bnpm"
    return Path.home() / ".local" / "share" / "bnpm"


def _resolve_default_bn_user_dir() -> Path:
    override = os.environ.get("BN_USER_DIRECTORY")
    if override:
        return Path(override).expanduser().resolve()

    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Binary Ninja"
    if system == "Windows":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "Binary Ninja"
        raise BnpmError("APPDATA is not set")
    return Path.home() / ".binaryninja"
