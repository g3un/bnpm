from __future__ import annotations

from pathlib import Path

from .models import LockedPackage, LockedPlugin, Lockfile
from .utils.atomic import write_text_atomically
from .utils.toml import load_toml


LOCK_VERSION = 1


def load_lockfile(path: Path) -> Lockfile:
    if not path.exists():
        return Lockfile(path=path, plugins=[], packages=[])
    data = load_toml(path)

    plugins = []
    for item in data.get("plugins", []):
        plugins.append(
            LockedPlugin(
                name=item["name"],
                source=item["source"],
                checksum=item["checksum"],
                version=item.get("version"),
                commit=item.get("commit"),
                dependencies=_parse_string_list(
                    item.get("dependencies", []), "plugins.dependencies"
                ),
            )
        )

    packages = []
    for item in data.get("packages", []):
        packages.append(
            LockedPackage(
                name=item["name"],
                source=item["source"],
                version=item["version"],
                checksum=item.get("checksum"),
                dependencies=_parse_string_list(
                    item.get("dependencies", []), "packages.dependencies"
                ),
            )
        )
    return Lockfile(path=path, plugins=plugins, packages=packages)


def write_lockfile(
    path: Path,
    plugins: list[LockedPlugin],
    packages: list[LockedPackage] | None = None,
) -> None:
    write_text_atomically(
        path, _format_lockfile(plugins, packages or []), allow_direct_fallback=True
    )


def _format_lockfile(plugins: list[LockedPlugin], packages: list[LockedPackage]) -> str:
    lines = [f"version = {LOCK_VERSION}", ""]
    for plugin in sorted(plugins, key=lambda item: item.name):
        lines.extend(
            [
                "[[plugins]]",
                f'name = "{_escape(plugin.name)}"',
                f'source = "{_escape(plugin.source)}"',
                f'checksum = "{_escape(plugin.checksum)}"',
            ]
        )
        if plugin.version is not None:
            lines.append(f'version = "{_escape(plugin.version)}"')
        if plugin.commit is not None:
            lines.append(f'commit = "{_escape(plugin.commit)}"')
        lines.extend(_format_string_list("dependencies", plugin.dependencies or []))
        lines.append("")

    for package in sorted(packages, key=lambda item: item.name):
        lines.extend(
            [
                "[[packages]]",
                f'name = "{_escape(package.name)}"',
                f'source = "{_escape(package.source)}"',
                f'version = "{_escape(package.version)}"',
            ]
        )
        if package.checksum is not None:
            lines.append(f'checksum = "{_escape(package.checksum)}"')
        lines.extend(
            _format_string_list("dependencies", sorted(package.dependencies or []))
        )
        lines.append("")
    return "\n".join(lines)


def merge_plugins(
    existing: list[LockedPlugin], updates: list[LockedPlugin]
) -> list[LockedPlugin]:
    merged = {plugin.name: plugin for plugin in existing}
    for plugin in updates:
        merged[plugin.name] = plugin
    return list(merged.values())


def _format_string_list(name: str, values: list[str]) -> list[str]:
    if not values:
        return [f"{name} = []"]
    lines = [f"{name} = ["]
    lines.extend(f'  "{_escape(value)}",' for value in values)
    lines.append("]")
    return lines


def _parse_string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return value


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
