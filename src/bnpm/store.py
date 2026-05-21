from __future__ import annotations

import os
import platform
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import url2pathname

from .source import SourceSpec


def project_root_from_manifest(manifest_path: Path) -> Path:
    return manifest_path.resolve().parent


def default_config_dir() -> Path:
    override = os.environ.get("BNPM_CONFIG_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if platform.system() == "Windows":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "bnpm"
    return Path.home() / ".config" / "bnpm"


def default_data_dir() -> Path:
    override = os.environ.get("BNPM_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "bnpm"
    return Path.home() / ".local" / "share" / "bnpm"


def default_manifest_path() -> Path:
    override = os.environ.get("BNPM_MANIFEST")
    if override:
        return Path(override).expanduser().resolve()
    return default_config_dir() / "bnpm.toml"


def default_lock_path() -> Path:
    override = os.environ.get("BNPM_LOCK")
    if override:
        return Path(override).expanduser().resolve()
    return default_config_dir() / "bnpm.lock"


def default_home() -> Path:
    override = os.environ.get("BNPM_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return default_data_dir() / "plugins"


def package_dir(home: Path) -> Path:
    return home.expanduser().resolve().parent / "packages"


def install_dir(home: Path, spec: SourceSpec, commit: str) -> Path:
    if spec.kind == "path":
        return Path(spec.path or "").expanduser().resolve()

    return plugin_dir(home, spec.name)


def plugin_dir_from_lock(home: Path, name: str, source: str, commit: str | None) -> Path:
    if commit is None:
        if source.startswith("file://"):
            return file_uri_to_path(source)
        return Path(source).expanduser().resolve()
    return plugin_dir(home, name)


def plugin_dir(home: Path, name: str, commit: str | None = None) -> Path:
    target = home.joinpath(_encode_path_segment(name)).resolve()
    home = home.resolve()
    if not target.is_relative_to(home):
        raise ValueError(f"plugin path escapes BNPM home: {name}")
    return target


def _encode_path_segment(value: str) -> str:
    if not value:
        raise ValueError("empty plugin path segment")
    return quote(value, safe="")


def path_to_file_uri(path: Path) -> str:
    return path.expanduser().resolve().as_uri()


def file_uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"not a file URI: {uri}")
    if parsed.netloc and parsed.netloc != "localhost":
        return Path(f"//{parsed.netloc}{url2pathname(parsed.path)}").resolve()
    return Path(url2pathname(parsed.path)).resolve()
