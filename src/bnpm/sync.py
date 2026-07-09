from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .config import get_config
from .dependencies import lock_dependencies
from .fetch import install
from .packages import install_packages
from .lockfile import write_lockfile
from .manifest import load_manifest
from .models import LockedPlugin, SourceSpec


def sync(
    manifest_path: Path | None = None,
    lock_path: Path | None = None,
    home: Path | None = None,
    report_progress=None,
) -> list[LockedPlugin]:
    config = get_config()
    manifest_path = manifest_path or config.bnpm_manifest_path
    lock_path = lock_path or config.bnpm_lock_path
    home = (home or config.bnpm_plugin_dir).expanduser().resolve()

    manifest = load_manifest(manifest_path)
    installed = [
        install(
            resolve_manifest_path_spec(spec, manifest.path.parent),
            home,
            report_progress=report_progress,
        )
        for spec in manifest.plugins.values()
    ]
    packages = install_packages(
        collect_requirements(installed), home, report_progress=report_progress
    )
    locked_plugins, locked_packages = lock_dependencies(installed, packages)
    write_lockfile(lock_path, locked_plugins, locked_packages)
    return locked_plugins


def resolve_manifest_path_spec(spec: SourceSpec, base: Path) -> SourceSpec:
    if spec.kind != "path" or spec.path is None:
        return spec
    path = Path(spec.path).expanduser()
    if path.is_absolute():
        return spec
    return replace(spec, path=str((base / path).resolve()))


def collect_requirements(plugins: list[LockedPlugin]) -> list[str]:
    requirements = []
    for plugin in plugins:
        requirements.extend(
            plugin.requirements
            if plugin.requirements is not None
            else plugin.dependencies or []
        )
    return requirements
