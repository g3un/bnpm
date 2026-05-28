from __future__ import annotations

import os
import platform
import subprocess
from functools import cache
from pathlib import Path

from ..errors import BnpmError


@cache
def find_bn_install_path() -> Path | None:
    for path in _collect_bn_install_roots(platform.system()):
        if path.exists():
            return path.resolve()
    return None


@cache
def get_bn_python_version(install_path: Path) -> str | None:
    python = _resolve_bn_python(install_path, platform.system())
    if python is None:
        return None
    result = subprocess.run(
        [
            str(python),
            "-c",
            "import sys; print('.'.join(str(part) for part in sys.version_info[:3]))",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _collect_bn_install_roots(system: str) -> list[Path]:
    roots = _collect_install_roots_from_lastrun(system)
    if system == "Darwin":
        roots.append(Path("/Applications/Binary Ninja.app"))
    elif system == "Windows":
        roots.extend(_collect_windows_install_roots())
    else:
        roots.extend(
            [
                Path.home() / "binaryninja",
                Path.home() / "Applications" / "binaryninja",
                Path("/opt/binaryninja"),
            ]
        )
    return _deduplicate_paths(roots)


def _collect_install_roots_from_lastrun(system: str) -> list[Path]:
    lastrun = _resolve_bn_user_dir(system) / "lastrun"
    if not lastrun.exists():
        return []
    value = lastrun.read_text(encoding="utf-8").strip()
    if not value:
        return []
    path = Path(value).expanduser()
    roots = []
    if path.suffix.lower() in {".exe", ".bin"} or path.is_file():
        roots.append(path.parent)
    roots.append(path)
    if system == "Darwin":
        for parent in [path, *path.parents]:
            if parent.suffix == ".app":
                roots.append(parent)
                break
    return roots


def _resolve_bn_user_dir(system: str) -> Path:
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


def _collect_windows_install_roots() -> list[Path]:
    roots = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        roots.append(Path(local_appdata) / "Vector35" / "BinaryNinja")
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        roots.append(Path(program_files) / "Vector35" / "BinaryNinja")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    if program_files_x86:
        roots.append(Path(program_files_x86) / "Vector35" / "BinaryNinja")
    return roots


def _resolve_bn_python(install_path: Path, system: str) -> Path | None:
    if system == "Windows":
        candidates = [install_path / "plugins" / "python" / "python.exe"]
    else:
        candidates = [
            install_path / "plugins" / "python" / "bin" / "python3",
            install_path / "plugins" / "python" / "bin" / "python",
        ]
    for path in candidates:
        if path.exists():
            return path.resolve()
    return None


def _deduplicate_paths(paths: list[Path]) -> list[Path]:
    unique = []
    seen = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique

