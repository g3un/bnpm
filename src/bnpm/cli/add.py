from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from argparse import ArgumentParser, Namespace

from ..config import get_config
from ..errors import BnpmError
from ..manifest import write_manifest
from ..models import SourceSpec
from ..source import parse_plugin
from .command import Command
from .common import ensure_clean_manifest_lock, load_or_empty_manifest
from .sync import sync_plugins


class AddCommand(Command):
    name = "add"

    @classmethod
    def configure_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument("name")
        source_group = parser.add_mutually_exclusive_group(required=True)
        source_group.add_argument("--git")
        source_group.add_argument("--path")
        ref_group = parser.add_mutually_exclusive_group()
        ref_group.add_argument("--tag")
        ref_group.add_argument("--branch")
        ref_group.add_argument("--rev")

    @classmethod
    def run(cls, args: Namespace) -> int:
        config = get_config()
        name = args.name
        git = args.git
        path = args.path
        tag = args.tag
        branch = args.branch
        rev = args.rev
        manifest_path = config.bnpm_manifest_path
        lock_path = config.bnpm_lock_path
        home = config.bnpm_plugin_dir

        ensure_clean_manifest_lock(manifest_path, lock_path)
        manifest = load_or_empty_manifest(manifest_path)

        if path is not None:
            if tag or branch or rev:
                raise BnpmError("local path plugins cannot set tag, branch, or rev")
            source_path = Path(path).expanduser()
            spec = parse_plugin(name, {"path": str(source_path.resolve())})
        else:
            assert git is not None
            spec = parse_plugin(name, git)
            spec = _apply_ref_options(spec, tag=tag, branch=branch, rev=rev)

        plugins = dict(manifest.plugins)
        plugins[name] = spec
        write_manifest(manifest_path, plugins)
        return sync_plugins(manifest_path, lock_path, home)


def _apply_ref_options(
    spec: SourceSpec,
    *,
    tag: str | None,
    branch: str | None,
    rev: str | None,
) -> SourceSpec:
    if not any((tag, branch, rev)):
        return spec
    if spec.kind == "path":
        raise BnpmError("local path plugins cannot set tag, branch, or rev")
    if spec.tag or spec.branch or spec.rev:
        raise BnpmError("plugin source already specifies a ref")
    return replace(spec, tag=tag, branch=branch, rev=rev)
