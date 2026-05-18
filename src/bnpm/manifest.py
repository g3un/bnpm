from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import ManifestError
from .source import SourceSpec, parse_plugin
from .toml_compat import load_toml


@dataclass(frozen=True)
class Manifest:
    path: Path
    version: int
    plugins: dict[str, SourceSpec]


def load_manifest(path: Path) -> Manifest:
    if not path.exists():
        raise ManifestError(f"manifest not found: {path}")

    try:
        data = load_toml(path)
    except ValueError as exc:
        raise ManifestError(f"invalid bnpm.toml: {exc}") from exc

    version = data.get("version")
    if not isinstance(version, int):
        raise ManifestError("version must be an integer")
    if version != 1:
        raise ManifestError(f"unsupported bnpm.toml version: {version}")

    plugins_data = data.get("plugins", {})
    if not isinstance(plugins_data, dict):
        raise ManifestError("[plugins] must be a table")

    plugins = {
        name: parse_plugin(name, value)
        for name, value in sorted(plugins_data.items())
    }
    return Manifest(path=path, version=version, plugins=plugins)
