from __future__ import annotations

from pathlib import Path

from .models import InstalledPlugin, LockedPlugin
from .utils.atomic import write_text_atomically
from .utils.toml import load_toml


METADATA_FILE = ".bnpm-installed.toml"
METADATA_VERSION = 1


def resolve_metadata_path(plugin_path: Path) -> Path:
    return plugin_path / METADATA_FILE


def write_installed_plugin(plugin_path: Path, plugin: LockedPlugin) -> None:
    write_text_atomically(
        resolve_metadata_path(plugin_path),
        _format_installed_plugin(plugin),
        allow_direct_fallback=True,
    )


def read_installed_plugin(plugin_path: Path) -> InstalledPlugin | None:
    path = resolve_metadata_path(plugin_path)
    if not path.exists():
        return None
    data = load_toml(path)
    if data.get("version") != METADATA_VERSION:
        return None
    return InstalledPlugin(
        name=_read_required_str(data, "name"),
        source=_read_required_str(data, "source"),
        checksum=_read_required_str(data, "checksum"),
        version=_read_optional_str(data, "plugin_version"),
        commit=_read_optional_str(data, "commit"),
    )


def does_installed_match_lock(installed: InstalledPlugin, locked: LockedPlugin) -> bool:
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


def _read_required_str(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{METADATA_FILE}: {key} must be a non-empty string")
    return value


def _read_optional_str(data: dict[str, object], key: str) -> str | None:
    if key not in data:
        return None
    return _read_required_str(data, key)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')



