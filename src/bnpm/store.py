from __future__ import annotations

import os
import platform
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import url2pathname

from .source import SourceSpec

SAFE_PATH_SEGMENT_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)


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

    assert spec.git is not None
    return plugin_dir(home, spec.git, commit)


def plugin_dir_from_lock(home: Path, source: str, commit: str | None) -> Path:
    if commit is None:
        if source.startswith("file://"):
            return file_uri_to_path(source)
        return Path(source).expanduser().resolve()
    return plugin_dir(home, source, commit)


def plugin_dir(home: Path, source: str, commit: str) -> Path:
    parts = _plugin_dir_parts(source)
    target = home.joinpath(*parts, commit).resolve()
    home = home.resolve()
    if not target.is_relative_to(home):
        raise ValueError(f"plugin path escapes BNPM home: {source}")
    return target


def _plugin_dir_parts(source: str) -> list[str]:
    parsed = urlparse(_normalize_git_source_for_parse(source))
    if not parsed.netloc:
        raise ValueError(f"git source is missing host: {source}")

    path = parsed.path.removesuffix(".git")
    parts = [parsed.netloc, *PurePosixPath(path).parts]
    clean = [part for part in parts if part not in {"", "/"}]
    if len(clean) < 3:
        raise ValueError(f"git source path is too short: {source}")
    return [_encode_path_segment(part) for part in clean]


def _encode_path_segment(value: str) -> str:
    if not value:
        raise ValueError("empty plugin path segment")
    encoded = []
    for char in value:
        if char in SAFE_PATH_SEGMENT_CHARS:
            encoded.append(char)
        else:
            encoded.extend(f"%{byte:02X}" for byte in char.encode("utf-8"))
    return "".join(encoded)


def _normalize_git_source_for_parse(source: str) -> str:
    if source.startswith("git@"):
        host_and_path = source.removeprefix("git@").replace(":", "/", 1)
        return f"ssh://{host_and_path}"
    return source


def path_to_file_uri(path: Path) -> str:
    return path.expanduser().resolve().as_uri()


def file_uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"not a file URI: {uri}")
    if parsed.netloc and parsed.netloc != "localhost":
        return Path(f"//{parsed.netloc}{url2pathname(parsed.path)}").resolve()
    return Path(url2pathname(parsed.path)).resolve()
