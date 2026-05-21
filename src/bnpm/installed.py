from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .atomic import atomic_write_text
from .lockfile import LockedPlugin
from .toml_compat import load_toml


METADATA_FILE = ".bnpm-installed.toml"
METADATA_VERSION = 1


@dataclass(frozen=True)
class InstalledPlugin:
    name: str
    source: str
    checksum: str
    version: str | None = None
    commit: str | None = None


def metadata_path(plugin_path: Path) -> Path:
    return plugin_path / METADATA_FILE


def write_installed_plugin(plugin_path: Path, plugin: LockedPlugin) -> None:
    atomic_write_text(
        metadata_path(plugin_path),
        _format_installed_plugin(plugin),
        allow_direct_fallback=True,
    )


def read_installed_plugin(plugin_path: Path) -> InstalledPlugin | None:
    path = metadata_path(plugin_path)
    if not path.exists():
        return None
    data = load_toml(path)
    if data.get("version") != METADATA_VERSION:
        return None
    return InstalledPlugin(
        name=_required_str(data, "name"),
        source=_required_str(data, "source"),
        checksum=_required_str(data, "checksum"),
        version=_optional_str(data, "plugin_version"),
        commit=_optional_str(data, "commit"),
    )


def installed_matches_lock(installed: InstalledPlugin, locked: LockedPlugin) -> bool:
    return (
        installed.name == locked.name
        and installed.source == locked.source
        and installed.version == locked.version
        and installed.commit == locked.commit
        and installed.checksum == locked.checksum
    )


def _format_installed_plugin(plugin: LockedPlugin) -> str:
    lines = [
        f"version = {METADATA_VERSION}",
        f'name = "{_escape(plugin.name)}"',
        f'source = "{_escape(plugin.source)}"',
        f'checksum = "{_escape(plugin.checksum)}"',
    ]
    if plugin.version is not None:
        lines.append(f'plugin_version = "{_escape(plugin.version)}"')
    if plugin.commit is not None:
        lines.append(f'commit = "{_escape(plugin.commit)}"')
    lines.append("")
    return "\n".join(lines)


def _required_str(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{METADATA_FILE}: {key} must be a non-empty string")
    return value


def _optional_str(data: dict[str, object], key: str) -> str | None:
    if key not in data:
        return None
    return _required_str(data, key)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
