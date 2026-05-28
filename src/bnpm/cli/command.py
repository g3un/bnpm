from __future__ import annotations

from argparse import ArgumentParser, Namespace
from typing import ClassVar


class Command:
    name: ClassVar[str]

    @classmethod
    def configure_parser(cls, parser: ArgumentParser) -> None:
        pass

    @classmethod
    def run(cls, args: Namespace) -> int:
        raise NotImplementedError
