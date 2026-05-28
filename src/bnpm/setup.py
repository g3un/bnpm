from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path

from .config import get_config
from .errors import BnpmError
from .helpers import find_bn_install_path
from .utils.python_env import resolve_bn_python_major_minor, resolve_venv_python


IGNORED_NAMES = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    # The Binary Ninja plugin bundle only needs runtime code; CLI commands run outside BN.
    "cli",
}


def setup_bn(plugin_dir: Path | None = None) -> Path:
    plugin_dir = plugin_dir.expanduser().resolve() if plugin_dir else get_config().bn_user_plugin_dir
    target = plugin_dir / "bnpm"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    return install_plugin_files(target)


def setup_bnpm_venv(venv_path: Path | None = None) -> Path:
    venv_path = venv_path.expanduser().resolve() if venv_path else get_config().bnpm_venv_dir
    venv_path.parent.mkdir(parents=True, exist_ok=True)
    if not resolve_venv_python(venv_path).exists():
        _create_venv(venv_path, resolve_bn_python_major_minor())

    install_api = resolve_bn_install_api()
    if install_api is None:
        raise BnpmError(
            "could not find Binary Ninja scripts/install_api.py; "
            "start Binary Ninja once and rerun setup"
        )
    _run_venv_python(venv_path, [str(install_api), "--force"])
    _run_venv_python(venv_path, ["-c", "import binaryninja"])
    return venv_path


def resolve_bn_install_api() -> Path | None:
    root = find_bn_install_path()
    if root is None:
        return None
    if platform.system() == "Darwin":
        path = root / "Contents" / "Resources" / "scripts" / "install_api.py"
    else:
        path = root / "scripts" / "install_api.py"
    if not path.exists():
        return None
    return path.resolve()


def _run_venv_python(venv_path: Path, args: list[str]) -> None:
    python = resolve_venv_python(venv_path)
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv_path)
    result = subprocess.run(
        [str(python), *args],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"{python} failed"
        raise BnpmError(message)


def _create_venv(venv_path: Path, python_version: str) -> None:
    result = subprocess.run(
        ["uv", "venv", "--python", python_version, str(venv_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "uv venv failed"
        raise BnpmError(message)


def install_plugin_files(output: Path) -> Path:
    output = output.expanduser().resolve()
    package_root = Path(__file__).resolve().parent
    _recreate_dir(output)
    shutil.copy2(package_root / "_binaryninja" / "plugin_init.py", output / "__init__.py")
    shutil.copytree(package_root, output / "bnpm", ignore=_ignore_generated)
    return output


def _recreate_dir(path: Path) -> None:
    try:
        if path.exists() or path.is_symlink():
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path, onerror=_make_writable_and_retry)
            else:
                path.unlink()
        path.mkdir(parents=True)
    except OSError as exc:
        raise BnpmError(
            f"could not replace Binary Ninja plugin directory {path}. "
            "Close Binary Ninja and check the directory permissions or read-only attributes."
        ) from exc


def _make_writable_and_retry(function, path, exc):
    os.chmod(path, stat.S_IWRITE)
    function(path)


def _ignore_generated(directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in IGNORED_NAMES}
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    ignored.update(name for name in names if name.endswith((".dist-info", ".egg-info")))
    return ignored
