from __future__ import annotations

import sys

from ..errors import BnpmError
from .parser import build_parser


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.command_handler.run(args)
    except BnpmError as exc:
        print(f"bnpm: {exc}", file=sys.stderr)
        return 1
