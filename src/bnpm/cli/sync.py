from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from ..config import get_config
from ..sync import sync
from .command import Command
from .common import report_progress


class SyncCommand(Command):
    name = "sync"

    @classmethod
    def run(cls, args: Namespace) -> int:
        config = get_config()
        return sync_plugins(config.bnpm_manifest_path, config.bnpm_lock_path, config.bnpm_plugin_dir)


def sync_plugins(manifest_path: Path, lock_path: Path, home: Path) -> int:
    installed = sync(manifest_path=manifest_path, lock_path=lock_path, home=home, report_progress=report_progress)
    for plugin in installed:
        print(f"synced {plugin.name} {plugin.version or 'local'} {plugin.commit or plugin.source}")
    return 0



