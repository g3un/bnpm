from __future__ import annotations

from argparse import Namespace

from ..setup import setup_bn, setup_bnpm_venv
from .command import Command


class SetupCommand(Command):
    name = "setup"

    @classmethod
    def run(cls, args: Namespace) -> int:
        target = setup_bn()
        venv_path = setup_bnpm_venv()
        print(f"installed BNPM Binary Ninja plugin to {target}")
        print(f"installed BNPM Python environment to {venv_path}")
        print("restart Binary Ninja to load BNPM")
        return 0
