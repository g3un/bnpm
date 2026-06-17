from __future__ import annotations

from argparse import Namespace
import sys

from ..config import get_config
from ..verify import verify_plugins
from .command import Command


class VerifyCommand(Command):
    name = "verify"

    @classmethod
    def run(cls, args: Namespace) -> int:
        config = get_config()
        results = verify_plugins(
            lock_path=config.bnpm_lock_path, home=config.bnpm_plugin_dir
        )
        failed = False
        for result in results:
            if result.ok:
                print(f"verified {result.plugin.name} {result.actual}")
            else:
                failed = True
                print(f"bnpm: {result.plugin.name}: {result.message}", file=sys.stderr)
        return 1 if failed else 0
