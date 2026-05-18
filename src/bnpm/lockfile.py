from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .atomic import atomic_write_text
from .toml_compat import load_toml


LOCK_VERSION = 1


@dataclass(frozen=True)
class LockedPlugin:
    name: str
    source: str
    checksum: str
    version: str | None = None
    commit: str | None = None
    dependencies: list[str] | None = None


@dataclass(frozen=True)
class LockedPackage:
    name: str
    source: str
    version: str
    checksum: str | None = None
    dependencies: list[str] | None = None


@dataclass(frozen=True)
class Lockfile:
    path: Path
    plugins: list[LockedPlugin]
    packages: list[LockedPackage]


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
                dependencies=_string_list(item.get("dependencies", []), "plugins.dependencies"),
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
                dependencies=_string_list(item.get("dependencies", []), "packages.dependencies"),
            )
        )
    return Lockfile(path=path, plugins=plugins, packages=packages)


def write_lockfile(
    path: Path,
    plugins: list[LockedPlugin],
    packages: list[LockedPackage] | None = None,
) -> None:
    atomic_write_text(path, _format_lockfile(plugins, packages or []), allow_direct_fallback=True)


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
        lines.extend(_format_string_list("dependencies", sorted(package.dependencies or [])))
        lines.append("")
    return "\n".join(lines)


def merge_plugins(existing: list[LockedPlugin], updates: list[LockedPlugin]) -> list[LockedPlugin]:
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


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return value


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
