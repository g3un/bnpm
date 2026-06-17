from __future__ import annotations

from functools import cache
import platform
from pathlib import Path

from ..config import get_config
from ..errors import BnpmError
from ..helpers import find_bn_install_path, get_bn_python_version


def resolve_venv_python(venv_path: Path | None = None) -> Path:
    if venv_path is None:
        return get_config().bnpm_venv_python
    venv_path = venv_path.expanduser().resolve()
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def resolve_package_python_executable() -> str:
    python = resolve_venv_python()
    if not python.exists():
        raise BnpmError("BNPM Python environment is missing; run `bnpm setup`")
    return str(python)


def build_uv_target_options() -> list[str]:
    return ["--python-version", resolve_bn_python_major_minor()]


def resolve_bn_python_major_minor() -> str:
    version = resolve_bn_python_version()
    parts = version.split(".")
    if len(parts) < 2:
        raise BnpmError(f"invalid Binary Ninja Python version: {version}")
    return ".".join(parts[:2])


@cache
def resolve_bn_python_version() -> str:
    root = find_bn_install_path()
    if root is None:
        raise BnpmError("could not find Binary Ninja install path")
    version = get_bn_python_version(root)
    if version is None:
        raise BnpmError("could not determine Binary Ninja Python version")
    return version
