from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .lockfile import Lockfile
from .manifest import Manifest, load_manifest
from .source import SourceSpec
from .store import path_to_file_uri
from .sync import resolve_manifest_path_spec


@dataclass(frozen=True)
class ManifestPlugin:
    name: str
    source: str
    version: str | None


def load_manifest_plugins(path: Path) -> dict[str, ManifestPlugin] | None:
    if not path.exists():
        return None
    manifest = load_manifest(path)
    return manifest_plugins(manifest)


def manifest_plugins(manifest: Manifest) -> dict[str, ManifestPlugin]:
    plugins = {}
    for name, spec in manifest.plugins.items():
        resolved = resolve_manifest_path_spec(spec, manifest.path.parent)
        plugins[name] = _manifest_plugin(name, resolved)
    return plugins


def lock_mismatches(
    manifest_plugins_by_name: dict[str, ManifestPlugin] | None,
    lockfile: Lockfile,
) -> list[str]:
    if manifest_plugins_by_name is None:
        return []

    messages = []
    locked = {plugin.name: plugin for plugin in lockfile.plugins}

    for name in sorted(set(manifest_plugins_by_name) - set(locked)):
        messages.append(f"plugin {name!r} is in bnpm.toml but not bnpm.lock")

    for name in sorted(set(locked) - set(manifest_plugins_by_name)):
        messages.append(f"plugin {name!r} is in bnpm.lock but not bnpm.toml")

    for name in sorted(set(manifest_plugins_by_name) & set(locked)):
        manifest_plugin = manifest_plugins_by_name[name]
        locked_plugin = locked[name]
        if manifest_plugin.source != locked_plugin.source:
            messages.append(f"plugin {name!r} source changed")
        if manifest_plugin.version != locked_plugin.version:
            messages.append(f"plugin {name!r} version changed")

    return messages


def _manifest_plugin(name: str, spec: SourceSpec) -> ManifestPlugin:
    if spec.kind == "path":
        assert spec.path is not None
        return ManifestPlugin(
            name=name,
            source=path_to_file_uri(Path(spec.path)),
            version=None,
        )

    assert spec.git is not None
    return ManifestPlugin(name=name, source=spec.git, version=spec.version)
