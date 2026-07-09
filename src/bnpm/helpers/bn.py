from __future__ import annotations

import os
import platform
import re
import subprocess
from functools import cache
from pathlib import Path

from ..errors import BnpmError


@cache
def find_bn_install_path() -> Path | None:
    root = _resolve_install_root_from_lastrun(platform.system())
    if root is None:
        return None
    return root.resolve()


@cache
def get_bn_python_version(install_path: Path) -> str | None:
    python = _resolve_bn_python(install_path, platform.system())
    if python is None:
        return None
    result = subprocess.run(
        [str(python), "-m", "sysconfig"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    match = re.search(r'Python version:\s+"([^"]+)"', result.stdout)
    if match is None:
        return None
    return match.group(1)


def _resolve_install_root_from_lastrun(system: str) -> Path | None:
    lastrun = resolve_bn_user_dir(system) / "lastrun"
    if not lastrun.exists():
        return None
    value = lastrun.read_text(encoding="utf-8").strip()
    if not value:
        return None
    path = Path(value).expanduser()
    if system == "Darwin":
        # On macOS, lastrun points somewhere inside the app bundle.
        root = path
        while root.suffix != ".app" and root != root.parent:
            root = root.parent
        if root.suffix != ".app":
            root = path
    elif system == "Windows":
        root = path.parent if path.suffix.lower() == ".exe" or path.is_file() else path
    else:
        root = path.parent if path.is_file() else path
    return root


def resolve_bn_user_dir(system: str) -> Path:
    override = os.environ.get("BN_USER_DIRECTORY")
    if override:
        return Path(override).expanduser().resolve()

    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Binary Ninja"
    if system == "Windows":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "Binary Ninja"
        raise BnpmError("APPDATA is not set")
    return Path.home() / ".binaryninja"


def _resolve_bn_python(install_path: Path, system: str) -> Path | None:
    if system == "Windows":
        path = install_path / "plugins" / "python" / "python.exe"
    elif system == "Darwin":
        path = install_path / "Contents" / "MacOS" / "bnpython3"
    else:
        path = install_path / "bnpython3"
    if not path.exists():
        return None
    return path.resolve()
