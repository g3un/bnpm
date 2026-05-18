from __future__ import annotations

import os
import platform
from pathlib import Path
from urllib.parse import urlparse
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


def install_dir(home: Path, spec: SourceSpec, commit: str) -> Path:
    if spec.kind == "path":
        return Path(spec.path or "").expanduser().resolve()

    assert spec.git is not None
    return managed_git_dir(home, spec.git, commit)


def plugin_dir_from_lock(home: Path, source: str, commit: str | None) -> Path:
    if commit is None:
        if source.startswith("file://"):
            return file_uri_to_path(source)
        return Path(source).expanduser().resolve()
    return managed_git_dir(home, source, commit)


def managed_git_dir(home: Path, source: str, commit: str) -> Path:
    clean = source
    for prefix in ("https://", "http://", "git@"):
        clean = clean.removeprefix(prefix)
    clean = clean.replace(":", "/").removesuffix(".git").strip("/")
    return home / clean / commit


def path_to_file_uri(path: Path) -> str:
    return path.expanduser().resolve().as_uri()


def file_uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"not a file URI: {uri}")
    if parsed.netloc and parsed.netloc != "localhost":
        return Path(f"//{parsed.netloc}{url2pathname(parsed.path)}").resolve()
    return Path(url2pathname(parsed.path)).resolve()
