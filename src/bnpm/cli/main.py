from __future__ import annotations

import sys

from ..config import get_config
from ..errors import BnpmError
from . import add, list, remove, setup, sync, update, verify
from .parser import build_parser


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = get_config()
    manifest_path = config.bnpm_manifest_path
    lock_path = config.bnpm_lock_path
    home = config.bnpm_plugin_dir

    try:
        if args.command == "add":
            return add.run(
                args.name,
                args.git,
                args.path,
                args.tag,
                args.branch,
                args.rev,
                manifest_path,
                lock_path,
                home,
            )
        if args.command == "remove":
            return remove.run(args.name, manifest_path, lock_path, home)
        if args.command == "update":
            return update.run(args.names, manifest_path, lock_path, home)
        if args.command == "sync":
            return sync.run(manifest_path, lock_path, home)
        if args.command == "verify":
            return verify.run(lock_path, home)
        if args.command == "list":
            return list.run(lock_path)
        if args.command == "setup":
            return setup.run()
    except BnpmError as exc:
        print(f"bnpm: {exc}", file=sys.stderr)
        return 1
    return 0


