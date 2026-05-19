from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

from .installer import install_plugin_files
from .errors import BnpmError


def setup_binaryninja(plugin_dir: Path | None = None) -> Path:
    plugin_dir = plugin_dir.expanduser().resolve() if plugin_dir else default_binaryninja_plugin_dir()
    target = plugin_dir / "bnpm"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    return install_plugin_files(target)


def default_binaryninja_plugin_dir() -> Path:
    override = os.environ.get("BNPM_BINARYNINJA_PLUGIN_DIR")
    if override:
        return Path(override).expanduser().resolve()

    return default_binaryninja_user_dir() / "plugins"


def default_binaryninja_user_dir() -> Path:
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
        raise BnpmError("APPDATA is not set; pass --plugin-dir")
    return Path.home() / ".binaryninja"


def default_binaryninja_python() -> Path | None:
    override = os.environ.get("BNPM_BINARYNINJA_PYTHON")
    if override:
        return Path(override).expanduser().resolve()

    for path in _binaryninja_python_candidates():
        if path.exists():
            return path.resolve()
    return None


def _binaryninja_python_candidates() -> list[Path]:
    system = platform.system()
    roots = _binaryninja_install_roots(system)
    candidates = []
    for root in roots:
        candidates.extend(_python_candidates_for_install_root(root, system))
    if system == "Windows":
        candidates.extend(_windows_install_root_candidates())
    if system != "Windows":
        candidates.extend(_which_candidates(("python3", "python")))
    return _unique_paths(candidates)


def _binaryninja_install_roots(system: str) -> list[Path]:
    roots = _install_roots_from_lastrun(system)
    if system == "Darwin":
        roots.append(Path("/Applications/Binary Ninja.app"))
    elif system == "Windows":
        roots.extend(_windows_install_roots())
    else:
        roots.extend(
            [
                Path.home() / "binaryninja",
                Path.home() / "Applications" / "binaryninja",
                Path("/opt/binaryninja"),
            ]
        )
    return _unique_paths(roots)


def _install_roots_from_lastrun(system: str) -> list[Path]:
    lastrun = default_binaryninja_user_dir() / "lastrun"
    if not lastrun.exists():
        return []
    value = lastrun.read_text(encoding="utf-8").strip()
    if not value:
        return []
    path = Path(value).expanduser()
    roots = [path]
    if path.suffix.lower() in {".exe", ".bin"} or path.name in {"binaryninja", "binaryninja.exe"}:
        roots.append(path.parent)
    if system == "Darwin":
        for parent in [path, *path.parents]:
            if parent.suffix == ".app":
                roots.append(parent)
                break
    return roots


def _python_candidates_for_install_root(root: Path, system: str) -> list[Path]:
    if system == "Darwin":
        return [
            root / "Contents" / "Frameworks" / "Python.framework" / "Versions" / "Current" / "bin" / "python3",
        ]
    if system == "Windows":
        return [
            root / "plugins" / "python" / "python.exe",
            root / "python" / "python.exe",
            root / "python.exe",
        ]
    return [
        root / "plugins" / "python" / "bin" / "python3",
        root / "python" / "bin" / "python3",
        root / "python3",
        root / "python",
    ]


def _windows_install_roots() -> list[Path]:
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


def _windows_install_root_candidates() -> list[Path]:
    candidates = []
    for root in _windows_install_roots():
        candidates.extend(_python_candidates_for_install_root(root, "Windows"))
    return candidates


def _which_candidates(names: tuple[str, ...]) -> list[Path]:
    candidates = []
    for name in names:
        path = shutil.which(name)
        if path is not None:
            candidates.append(Path(path))
    return candidates


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique = []
    seen = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique
