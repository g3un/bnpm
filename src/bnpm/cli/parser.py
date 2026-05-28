from __future__ import annotations

import argparse
from collections.abc import Sequence

from .add import AddCommand
from .command import Command
from .list import ListCommand
from .remove import RemoveCommand
from .setup import SetupCommand
from .sync import SyncCommand
from .update import UpdateCommand
from .verify import VerifyCommand


DEFAULT_COMMANDS: tuple[type[Command], ...] = (
    AddCommand,
    RemoveCommand,
    UpdateCommand,
    SyncCommand,
    VerifyCommand,
    ListCommand,
    SetupCommand,
)


def build_parser(commands: Sequence[type[Command]] = DEFAULT_COMMANDS) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bnpm")

    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in commands:
        command_parser = subparsers.add_parser(command.name)
        command.configure_parser(command_parser)
        command_parser.set_defaults(command_handler=command)

    return parser
