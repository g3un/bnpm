from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import url2pathname

from ..config import get_config
from ..models import SourceSpec


def resolve_package_dir(home: Path) -> Path:
    config = get_config()
    if home.expanduser().resolve() == config.bnpm_plugin_dir.resolve():
        return config.bnpm_package_dir
    return home.expanduser().resolve().parent / "packages"


def resolve_install_dir(home: Path, spec: SourceSpec) -> Path:
    if spec.kind == "path":
        return Path(spec.path or "").expanduser().resolve()

    return resolve_plugin_dir(home, spec.name)


def resolve_plugin_dir_from_lock(
    home: Path, name: str, source: str, commit: str | None
) -> Path:
    if commit is None:
        if source.startswith("file://"):
            return convert_file_uri_to_path(source)
        return Path(source).expanduser().resolve()
    return resolve_plugin_dir(home, name)


def resolve_plugin_dir(home: Path, name: str) -> Path:
    target = home.joinpath(_encode_path_segment(name)).resolve()
    home = home.resolve()
    if not target.is_relative_to(home):
        raise ValueError(f"plugin path escapes BNPM home: {name}")
    return target


def convert_path_to_file_uri(path: Path) -> str:
    return path.expanduser().resolve().as_uri()


def convert_file_uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"not a file URI: {uri}")
    if parsed.netloc and parsed.netloc != "localhost":
        return Path(f"//{parsed.netloc}{url2pathname(parsed.path)}").resolve()
    return Path(url2pathname(parsed.path)).resolve()


def _encode_path_segment(value: str) -> str:
    if not value:
        raise ValueError("empty plugin path segment")
    return quote(value, safe="")
