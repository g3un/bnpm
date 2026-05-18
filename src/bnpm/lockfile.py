from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .toml_compat import load_toml


LOCK_VERSION = 1


@dataclass(frozen=True)
class LockedPlugin:
    name: str
    source: str
    checksum: str
    version: str | None = None
    commit: str | None = None


@dataclass(frozen=True)
class Lockfile:
    path: Path
    plugins: list[LockedPlugin]


def load_lockfile(path: Path) -> Lockfile:
    if not path.exists():
        return Lockfile(path=path, plugins=[])
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
            )
        )
    return Lockfile(path=path, plugins=plugins)


def write_lockfile(path: Path, plugins: list[LockedPlugin]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def merge_plugins(existing: list[LockedPlugin], updates: list[LockedPlugin]) -> list[LockedPlugin]:
    merged = {plugin.name: plugin for plugin in existing}
    for plugin in updates:
        merged[plugin.name] = plugin
    return list(merged.values())


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
