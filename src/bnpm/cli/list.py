from __future__ import annotations

from argparse import Namespace

from ..config import get_config
from ..lockfile import load_lockfile
from .command import Command


class ListCommand(Command):
    name = "list"

    @classmethod
    def run(cls, args: Namespace) -> int:
        config = get_config()
        lockfile = load_lockfile(config.bnpm_lock_path)
        for plugin in sorted(lockfile.plugins, key=lambda item: item.name):
            print(f"{plugin.name}\t{plugin.version or 'local'}\t{plugin.commit or plugin.source}")
        return 0
