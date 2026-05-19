from __future__ import annotations

from dataclasses import replace
from importlib import metadata
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .errors import BnpmError
from .lockfile import LockedPackage, LockedPlugin
from .setup import default_binaryninja_python
from .store import package_dir

REQ_NAME_RE = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def install_packages(requirements: list[str], home: Path, progress=None) -> list[LockedPackage]:
    target = package_dir(home)
    if not requirements:
        target.mkdir(parents=True, exist_ok=True)
        return []

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        _progress(progress, f"recreating package directory {target}")
        shutil.rmtree(target)
    target.mkdir()

    with tempfile.TemporaryDirectory(prefix="bnpm-deps-") as temp:
        temp_path = Path(temp)
        requirements_path = temp_path / "requirements.txt"
        requirements_path.write_text(
            "".join(f"{requirement}\n" for requirement in sorted(set(requirements))),
            encoding="utf-8",
            newline="",
        )
        _progress(progress, f"installing {len(set(requirements))} package requirement(s) into {target}")
        _install_requirements(requirements_path, target)
        packages = _packages_from_target(target)
        _progress(progress, f"installed {len(packages)} package(s)")
        return packages


def _progress(progress, message: str) -> None:
    if progress is not None:
        progress(message)


def _install_requirements(requirements_path: Path, target: Path) -> None:
    try:
        _run_uv_install(requirements_path, target)
    except FileNotFoundError:
        _run_pip_install(requirements_path, target)
    except BnpmError:
        _run_pip_install(requirements_path, target)


def _run_uv_install(requirements_path: Path, target: Path) -> None:
    python = _python_executable()
    result = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            python,
            "--target",
            str(target),
            "--reinstall",
            "-r",
            str(requirements_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "uv pip install failed"
        raise BnpmError(message)


def _run_pip_install(requirements_path: Path, target: Path) -> None:
    python = _python_executable()
    result = subprocess.run(
        [
            python,
            "-m",
            "pip",
            "--isolated",
            "install",
            "--disable-pip-version-check",
            "--ignore-installed",
            "--upgrade",
            "--upgrade-strategy",
            "only-if-needed",
            "--target",
            str(target),
            "-r",
            str(requirements_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 and "No module named pip" in result.stderr:
        _ensure_pip()
        result = subprocess.run(
            [
                python,
                "-m",
                "pip",
                "--isolated",
                "install",
                "--disable-pip-version-check",
                "--ignore-installed",
                "--upgrade",
                "--upgrade-strategy",
                "only-if-needed",
                "--target",
                str(target),
                "-r",
                str(requirements_path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "pip install failed"
        raise BnpmError(message)


def _ensure_pip() -> None:
    python = _python_executable()
    result = subprocess.run(
        [python, "-m", "ensurepip", "--upgrade"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "pip is not available"
        raise BnpmError(message)


def _python_executable() -> str:
    configured = _configured_python()
    if configured is not None:
        return str(configured)
    binaryninja_python = default_binaryninja_python()
    if binaryninja_python is not None:
        return str(binaryninja_python)
    binaryninja_python = Path(sys.prefix) / "bin" / "python3"
    if binaryninja_python.exists():
        return str(binaryninja_python)
    for name in ("python3", "python"):
        path = shutil.which(name)
        if path is not None:
            return path
    return sys.executable


def _configured_python() -> Path | None:
    override = os.environ.get("BNPM_BINARYNINJA_PYTHON")
    if override:
        path = Path(override).expanduser().resolve()
        if path.exists():
            return path
    return None


def _packages_from_target(target: Path) -> list[LockedPackage]:
    packages = []
    for distribution in metadata.distributions(path=[str(target)]):
        package_metadata = distribution.metadata
        name = package_metadata["Name"]
        version = distribution.version
        packages.append(
            LockedPackage(
                name=name,
                source="pypi",
                version=f"pypi:{version}",
                dependencies=package_metadata.get_all("Requires-Dist") or [],
            )
        )
    return packages


def lock_dependencies(
    plugins: list[LockedPlugin],
    packages: list[LockedPackage],
) -> tuple[list[LockedPlugin], list[LockedPackage]]:
    pins = {_normalize_name(package.name): _pin(package) for package in packages}
    locked_plugins = [
        replace(plugin, dependencies=_resolved_pins(plugin.requirements or [], pins), requirements=None)
        for plugin in plugins
    ]
    locked_packages = [
        replace(package, dependencies=_resolved_pins(package.dependencies or [], pins))
        for package in packages
    ]
    return locked_plugins, locked_packages


def _resolved_pins(requirements: list[str], pins: dict[str, str]) -> list[str]:
    resolved = []
    for requirement in requirements:
        name = _requirement_name(requirement)
        if name is None:
            continue
        pin = pins.get(_normalize_name(name))
        if pin is not None:
            resolved.append(pin)
    return sorted(set(resolved))


def _requirement_name(requirement: str) -> str | None:
    match = REQ_NAME_RE.match(requirement)
    if match is None:
        return None
    return match.group(1)


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _pin(package: LockedPackage) -> str:
    version = package.version.removeprefix("pypi:")
    return f"{package.name}=={version}"
