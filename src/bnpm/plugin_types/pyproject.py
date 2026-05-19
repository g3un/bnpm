from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable

from ..errors import FetchError
from ..toml_compat import load_toml


Warn = Callable[[str], None]


def read_project_dependencies(path: Path) -> list[str]:
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


def resolve_entry(name: str, plugin_path: Path, warn: Warn) -> tuple[Path, Path] | None:
    pyproject_path = plugin_path / "pyproject.toml"
    pyproject = _load_pyproject(pyproject_path, warn)
    if pyproject is None:
        return None

    explicit = _tool_bnpm_entry(name, plugin_path, pyproject, warn)
    if explicit is not None:
        return explicit

    project_name = _pyproject_name(pyproject)
    if not project_name:
        return None

    package_name = _import_package_name(project_name)
    init_path = plugin_path / "src" / package_name / "__init__.py"
    if init_path.exists():
        return init_path, plugin_path / "src"
    return None


def _load_pyproject(path: Path, warn: Warn) -> dict[str, Any] | None:
    try:
        return load_toml(path)
    except Exception as exc:
        warn(f"could not read {path}: {exc}")
        return None


def _tool_bnpm_entry(name: str, plugin_path: Path, pyproject: dict[str, Any], warn: Warn) -> tuple[Path, Path] | None:
    tool = pyproject.get("tool", {})
    if not isinstance(tool, dict):
        return None
    if "bnpm" not in tool:
        return None
    bnpm = tool.get("bnpm")
    if not isinstance(bnpm, dict):
        warn(f"skipped {name}: [tool.bnpm] must be a table")
        return None
    if not bnpm:
        return None
    package = bnpm.get("package")
    source = bnpm.get("source", ".")
    if not isinstance(package, str) or not package:
        warn(f"skipped {name}: [tool.bnpm].package must be a string")
        return None
    if not isinstance(source, str) or not source:
        warn(f"skipped {name}: [tool.bnpm].source must be a string")
        return None
    import_base = (plugin_path / source).resolve()
    init_path = import_base / package / "__init__.py"
    if not _is_relative_to(import_base, plugin_path.resolve()):
        warn(f"skipped {name}: [tool.bnpm].source escapes plugin directory")
        return None
    if not init_path.exists():
        warn(f"skipped {name}: missing {init_path}")
        return None
    return init_path, import_base


def _pyproject_name(data: dict[str, Any]) -> str | None:
    project = data.get("project", {})
    if not isinstance(project, dict):
        return None
    name = project.get("name")
    if not isinstance(name, str) or not name:
        return None
    return name


def _import_package_name(project_name: str) -> str:
    return re.sub(r"[-.]+", "_", project_name)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
