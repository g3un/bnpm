from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import FetchError
from .hash import tree_sha256
from .lockfile import LockedPlugin
from .source import SourceSpec
from .store import install_dir, path_to_file_uri
from .toml_compat import load_toml


def install(spec: SourceSpec, home: Path, progress=None) -> LockedPlugin:
    if spec.kind == "path":
        return _lock_path_spec(spec, home, progress=progress)
    return _install_git_spec(spec, home, progress=progress)


def _lock_path_spec(spec: SourceSpec, home: Path, progress=None) -> LockedPlugin:
    if not spec.path:
        raise FetchError(f"{spec.name}: path source is missing path")
    path = Path(spec.path).expanduser().resolve()
    if not path.exists():
        raise FetchError(f"{spec.name}: local path does not exist: {path}")
    checksum = tree_sha256(path)
    return LockedPlugin(
        name=spec.name,
        source=path_to_file_uri(path),
        version=spec.version,
        checksum=checksum,
        requirements=_read_requirements(path, progress=progress),
    )


def _install_git_spec(spec: SourceSpec, home: Path, progress=None) -> LockedPlugin:
    if not spec.git:
        raise FetchError(f"{spec.name}: git source is missing URL")

    with tempfile.TemporaryDirectory(prefix="bnpm-") as temp:
        checkout = Path(temp) / "checkout"
        _run(["git", "clone", "--quiet", spec.git, str(checkout)], cwd=None)
        _checkout(spec, checkout)
        commit = _capture(["git", "rev-parse", "HEAD"], cwd=checkout)
        target = install_dir(home, spec, commit)

        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(checkout, target, ignore=shutil.ignore_patterns(".git"))

    checksum = tree_sha256(target)
    return LockedPlugin(
        name=spec.name,
        source=spec.git,
        version=spec.version,
        commit=commit,
        checksum=checksum,
        requirements=_read_requirements(target, progress=progress),
    )


def _checkout(spec: SourceSpec, checkout: Path) -> None:
    if spec.tag:
        _run(["git", "checkout", "--quiet", f"tags/{spec.tag}"], cwd=checkout)
    elif spec.rev:
        _run(["git", "checkout", "--quiet", spec.rev], cwd=checkout)
    elif spec.branch:
        _run(["git", "checkout", "--quiet", spec.branch], cwd=checkout)


def _run(args: list[str], cwd: Path | None) -> None:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise FetchError(message)


def _capture(args: list[str], cwd: Path) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise FetchError(message)
    return result.stdout.strip()


def _read_requirements(plugin_path: Path, progress=None) -> list[str]:
    pyproject_path = plugin_path / "pyproject.toml"
    requirements_path = plugin_path / "requirements.txt"
    if pyproject_path.exists():
        if requirements_path.exists():
            _progress(progress, f"ignored {requirements_path}: pyproject.toml is present")
        return _read_pyproject_dependencies(pyproject_path)

    if not requirements_path.exists():
        return []

    dependencies = []
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        requirement = line.strip()
        if not requirement or requirement.startswith("#"):
            continue
        dependencies.append(requirement)
    return dependencies


def _read_pyproject_dependencies(path: Path) -> list[str]:
    try:
        data = load_toml(path)
    except ValueError as exc:
        raise FetchError(f"invalid pyproject.toml: {exc}") from exc
    project = data.get("project", {})
    if not isinstance(project, dict):
        return []
    dependencies = project.get("dependencies", [])
    if dependencies is None:
        return []
    if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
        raise FetchError("[project].dependencies must be a list of strings")
    return dependencies


def _progress(progress, message: str) -> None:
    if progress is not None:
        progress(message)
