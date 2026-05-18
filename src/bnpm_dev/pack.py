from __future__ import annotations

import argparse
from pathlib import Path
import shutil
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


DEFAULT_OUTPUT = Path("bundle") / "bnpm"
IGNORED_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pack.py",
        description="Build a Binary Ninja plugin directory for BNPM.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output plugin directory, default: {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    output = _resolve_output(root, args.output)

    _recreate_dir(output)
    _copy_file(root / "binaryninja" / "__init__.py", output / "__init__.py")
    _copy_file(root / "binaryninja" / "plugin.json", output / "plugin.json")
    _copy_file(root / "LICENSE", output / "LICENSE")
    _write_requirements(root / "pyproject.toml", output / "requirements.txt")
    _copy_tree(root / "src" / "bnpm", output / "bnpm")

    print(f"packed Binary Ninja plugin: {output}")
    return 0


def _resolve_output(root: Path, output: Path) -> Path:
    if not output.is_absolute():
        output = root / output
    return output.resolve()


def _recreate_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, ignore=_ignore_generated)


def _write_requirements(pyproject_path: Path, target: Path) -> None:
    dependencies = _project_dependencies(pyproject_path)
    content = "".join(f"{dependency}\n" for dependency in dependencies)
    target.write_text(content, encoding="utf-8", newline="")


def _project_dependencies(pyproject_path: Path) -> list[str]:
    with pyproject_path.open("rb") as handle:
        pyproject: dict[str, Any] = tomllib.load(handle)
    project = pyproject.get("project", {})
    if not isinstance(project, dict):
        raise ValueError("[project] must be a table")
    dependencies = project.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
        raise ValueError("[project].dependencies must be a list of strings")
    return dependencies


def _ignore_generated(directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in IGNORED_NAMES}
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    return ignored


if __name__ == "__main__":
    raise SystemExit(main())
