from __future__ import annotations

from pathlib import Path
import shutil


IGNORED_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def install_plugin_files(output: Path) -> Path:
    output = output.expanduser().resolve()
    _recreate_dir(output)
    _copy_plugin_resource("plugin_init.py", output / "__init__.py")
    _copy_package(output / "bnpm")
    return output


def _recreate_dir(path: Path) -> None:
    if path.exists() or path.is_symlink():
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    path.mkdir(parents=True)


def _copy_plugin_resource(name: str, target: Path) -> None:
    shutil.copy2(_package_root() / "_binaryninja" / name, target)


def _copy_package(target: Path) -> None:
    shutil.copytree(_package_root(), target, ignore=_ignore_generated)


def _package_root() -> Path:
    return Path(__file__).resolve().parent


def _ignore_generated(directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in IGNORED_NAMES}
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    ignored.update(name for name in names if name.endswith((".dist-info", ".egg-info")))
    return ignored
