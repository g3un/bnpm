from __future__ import annotations

from pathlib import Path

from .errors import BnpmError
from .models import Manifest, SourceSpec
from .source import parse_plugin
from .utils.atomic import write_text_atomically
from .utils.toml import load_toml


def load_manifest(path: Path) -> Manifest:
    if not path.exists():
        raise BnpmError(f"manifest not found: {path}")

    try:
        data = load_toml(path)
    except ValueError as exc:
        raise BnpmError(f"invalid bnpm.toml: {exc}") from exc

    version = data.get("version")
    if not isinstance(version, int):
        raise BnpmError("version must be an integer")
    if version != 1:
        raise BnpmError(f"unsupported bnpm.toml version: {version}")

    plugins_data = data.get("plugins", {})
    if not isinstance(plugins_data, dict):
        raise BnpmError("[plugins] must be a table")

    plugins = {
        name: parse_plugin(name, value) for name, value in sorted(plugins_data.items())
    }
    return Manifest(path=path, version=version, plugins=plugins)


def write_manifest(path: Path, plugins: dict[str, SourceSpec]) -> None:
    write_text_atomically(path, _format_manifest(plugins), allow_direct_fallback=True)


def _format_manifest(plugins: dict[str, SourceSpec]) -> str:
    lines = ["version = 1", "", "[plugins]"]
    for name, spec in sorted(plugins.items()):
        lines.append(f"{name} = {_format_plugin(spec)}")
    lines.append("")
    return "\n".join(lines)


def _format_plugin(spec: SourceSpec) -> str:
    if spec.kind == "path":
        assert spec.path is not None
        return f'{{ path = "{_escape(spec.path)}" }}'

    assert spec.git is not None
    fields = [f'git = "{_escape(spec.git)}"']
    if spec.tag:
        fields.append(f'tag = "{_escape(spec.tag)}"')
    if spec.branch:
        fields.append(f'branch = "{_escape(spec.branch)}"')
    if spec.rev:
        fields.append(f'rev = "{_escape(spec.rev)}"')
    return "{ " + ", ".join(fields) + " }"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
