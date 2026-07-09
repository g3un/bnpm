from __future__ import annotations

from importlib import metadata
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import BnpmError
from .models import LockedPackage
from .utils.python_env import resolve_package_python_executable, build_uv_target_options
from .utils.locations import resolve_package_dir


def install_packages(
    requirements: list[str], home: Path, report_progress=None
) -> list[LockedPackage]:
    target = resolve_package_dir(home)
    if not requirements:
        target.mkdir(parents=True, exist_ok=True)
        return []

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if report_progress:
            report_progress(f"recreating package directory {target}")
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
        if report_progress:
            report_progress(
                f"installing {len(set(requirements))} package requirement(s) into {target}"
            )
        _install_requirements(requirements_path, target)
        packages = _collect_packages_from_target(target)
        if report_progress:
            report_progress(f"installed {len(packages)} package(s)")
        return packages


def _install_requirements(requirements_path: Path, target: Path) -> None:
    try:
        _run_uv_install(requirements_path, target)
    except FileNotFoundError:
        _run_pip_install(requirements_path, target)
    except BnpmError:
        _run_pip_install(requirements_path, target)


def _run_uv_install(requirements_path: Path, target: Path) -> None:
    result = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            *build_uv_target_options(),
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
        message = (
            result.stderr.strip() or result.stdout.strip() or "uv pip install failed"
        )
        raise BnpmError(message)


def _run_pip_install(requirements_path: Path, target: Path) -> None:
    python = resolve_package_python_executable()
    result = subprocess.run(
        _build_pip_install_command(python, requirements_path, target),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 and "No module named pip" in result.stderr:
        _ensure_pip()
        result = subprocess.run(
            _build_pip_install_command(python, requirements_path, target),
            text=True,
            capture_output=True,
            check=False,
        )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "pip install failed"
        raise BnpmError(message)


def _build_pip_install_command(
    python: str, requirements_path: Path, target: Path
) -> list[str]:
    return [
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
    ]


def _ensure_pip() -> None:
    python = resolve_package_python_executable()
    result = subprocess.run(
        [python, "-m", "ensurepip", "--upgrade"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = (
            result.stderr.strip() or result.stdout.strip() or "pip is not available"
        )
        raise BnpmError(message)


def _collect_packages_from_target(target: Path) -> list[LockedPackage]:
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
