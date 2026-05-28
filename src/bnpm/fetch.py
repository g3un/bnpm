from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import FetchError
from .utils.hash import compute_tree_sha256
from .installed import write_installed_plugin
from .models import LockedPlugin, SourceSpec
from .plugin_types import legacy_python, pyproject
from .utils.locations import resolve_install_dir, convert_path_to_file_uri


def install(spec: SourceSpec, home: Path, report_progress=None) -> LockedPlugin:
    if spec.kind == "path":
        return _lock_path_spec(spec, home, report_progress=report_progress)
    return _install_git_spec(spec, home, report_progress=report_progress)


def _lock_path_spec(spec: SourceSpec, home: Path, report_progress=None) -> LockedPlugin:
    if not spec.path:
        raise FetchError(f"{spec.name}: path source is missing path")
    path = Path(spec.path).expanduser().resolve()
    if not path.exists():
        raise FetchError(f"{spec.name}: local path does not exist: {path}")
    checksum = compute_tree_sha256(path)
    return LockedPlugin(
        name=spec.name,
        source=convert_path_to_file_uri(path),
        version=spec.version,
        checksum=checksum,
        requirements=_read_requirements(path, report_progress=report_progress),
    )


def _install_git_spec(spec: SourceSpec, home: Path, report_progress=None) -> LockedPlugin:
    if not spec.git:
        raise FetchError(f"{spec.name}: git source is missing URL")

    with tempfile.TemporaryDirectory(prefix="bnpm-") as temp:
        checkout = Path(temp) / "checkout"
        _run_git(["git", "clone", "--quiet", spec.git, str(checkout)], cwd=None)
        _checkout(spec, checkout)
        commit = _run_git(["git", "rev-parse", "HEAD"], cwd=checkout)
        target = resolve_install_dir(home, spec)
        staged = target.parent / f".{target.name}.{commit}.tmp"

        if staged.exists():
            shutil.rmtree(staged)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(checkout, staged, ignore=shutil.ignore_patterns(".git"))

        checksum = compute_tree_sha256(staged)
        locked = LockedPlugin(
            name=spec.name,
            source=spec.git,
            version=spec.version,
            commit=commit,
            checksum=checksum,
            requirements=_read_requirements(staged, report_progress=report_progress),
        )
        write_installed_plugin(staged, locked)
        _replace_tree(staged, target)
        return locked


def _checkout(spec: SourceSpec, checkout: Path) -> None:
    if spec.tag:
        _run_git(["git", "checkout", "--quiet", f"tags/{spec.tag}"], cwd=checkout)
    elif spec.rev:
        _run_git(["git", "checkout", "--quiet", spec.rev], cwd=checkout)
    elif spec.branch:
        _run_git(["git", "checkout", "--quiet", spec.branch], cwd=checkout)


def _run_git(args: list[str], cwd: Path | None) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise FetchError(message)
    return result.stdout.strip()


def _replace_tree(staged: Path, target: Path) -> None:
    backup = target.parent / f".{target.name}.previous.tmp"
    if backup.exists():
        shutil.rmtree(backup)
    try:
        if target.exists():
            target.rename(backup)
        staged.rename(target)
    except Exception:
        if staged.exists():
            shutil.rmtree(staged)
        if not target.exists() and backup.exists():
            backup.rename(target)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _read_requirements(plugin_path: Path, report_progress=None) -> list[str]:
    pyproject_path = plugin_path / "pyproject.toml"
    requirements_path = plugin_path / "requirements.txt"
    if pyproject_path.exists():
        if requirements_path.exists():
            _report_progress(report_progress, f"ignored {requirements_path}: pyproject.toml is present")
        return pyproject.read_project_dependencies(pyproject_path)

    if not requirements_path.exists():
        return []

    return legacy_python.read_requirements_txt(requirements_path)


def _report_progress(report_progress, message: str) -> None:
    if report_progress is not None:
        report_progress(message)







