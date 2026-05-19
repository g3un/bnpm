from __future__ import annotations

from pathlib import Path


def read_requirements_txt(path: Path) -> list[str]:
    dependencies = []
    for line in path.read_text(encoding="utf-8").splitlines():
        requirement = line.strip()
        if not requirement or requirement.startswith("#"):
            continue
        dependencies.append(requirement)
    return dependencies


def resolve_entry(plugin_path: Path) -> tuple[Path, Path] | None:
    init_path = plugin_path / "__init__.py"
    if init_path.exists():
        return init_path, plugin_path
    return None
