from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence

from . import add, list as list_, remove, setup, sync, update, verify

CommandSpec = tuple[str, Callable[[argparse.ArgumentParser], None] | None, Callable]

DEFAULT_COMMANDS: tuple[CommandSpec, ...] = (
    ("add", add.configure_parser, add.run),
    ("remove", remove.configure_parser, remove.run),
    ("update", update.configure_parser, update.run),
    ("sync", None, sync.run),
    ("verify", None, verify.run),
    ("list", None, list_.run),
    ("setup", None, setup.run),
)


def build_parser(
    commands: Sequence[CommandSpec] = DEFAULT_COMMANDS,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bnpm")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, configure, run in commands:
        command_parser = subparsers.add_parser(name)
        if configure is not None:
            configure(command_parser)
        command_parser.set_defaults(command_handler=run)
    return parser
