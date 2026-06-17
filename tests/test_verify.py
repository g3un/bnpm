from __future__ import annotations

import contextlib
import io
import tempfile
import types
from pathlib import Path
import unittest

from bnpm.cli.main import run_cli
from bnpm.installed import write_installed_plugin
from bnpm.utils.hash import compute_tree_sha256
from bnpm.lockfile import LockedPlugin, write_lockfile
from bnpm.utils.locations import (
    resolve_plugin_dir,
)
from tests.helpers import clear_bnpm_caches


class VerifyTests(unittest.TestCase):
    def setUp(self):
        clear_bnpm_caches()

    def test_verify_detects_tampered_git_plugin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            plugin = resolve_plugin_dir(home, "tampered")
            plugin.mkdir(parents=True)
            init_path = plugin / "__init__.py"
            init_path.write_text("VALUE = 1\n", encoding="utf-8")
            locked = LockedPlugin(
                name="tampered",
                source="https://github.com/user/plugin.git",
                version="HEAD",
                checksum=compute_tree_sha256(plugin),
                commit="abc123",
            )
            write_installed_plugin(plugin, locked)
            init_path.write_text("VALUE = 2\n", encoding="utf-8")
            lock = root / "bnpm.lock"
            write_lockfile(lock, [locked])

            stderr = io.StringIO()
            with (
                patch_verify_config(root / "bnpm.lock", home),
                contextlib.redirect_stderr(stderr),
            ):
                code = run_cli(["verify"])

            self.assertEqual(code, 1)
            self.assertIn("tampered: checksum mismatch", stderr.getvalue())

    def test_verify_accepts_installed_metadata_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            plugin = resolve_plugin_dir(home, "stable")
            plugin.mkdir(parents=True)
            plugin.joinpath("__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            locked = LockedPlugin(
                name="stable",
                source="https://github.com/user/plugin.git",
                version="HEAD",
                checksum=compute_tree_sha256(plugin),
                commit="abc123",
            )
            write_installed_plugin(plugin, locked)
            lock = root / "bnpm.lock"
            write_lockfile(lock, [locked])

            stdout = io.StringIO()
            with (
                patch_verify_config(root / "bnpm.lock", home),
                contextlib.redirect_stdout(stdout),
            ):
                code = run_cli(["verify"])

            self.assertEqual(code, 0)
            self.assertIn("verified stable", stdout.getvalue())

    def test_verify_reports_missing_plugin_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            lock = root / "bnpm.lock"
            write_lockfile(
                lock,
                [
                    LockedPlugin(
                        name="missing",
                        source="https://github.com/user/plugin.git",
                        version="HEAD",
                        checksum="sha256:missing",
                        commit="abc123",
                    )
                ],
            )

            stderr = io.StringIO()
            with (
                patch_verify_config(root / "bnpm.lock", home),
                contextlib.redirect_stderr(stderr),
            ):
                code = run_cli(["verify"])

            self.assertEqual(code, 1)
            self.assertIn("missing: missing plugin path", stderr.getvalue())


def patch_verify_config(lock_path: Path, home: Path):
    from unittest.mock import patch

    return patch(
        "bnpm.cli.verify.get_config",
        return_value=types.SimpleNamespace(
            bnpm_lock_path=lock_path,
            bnpm_plugin_dir=home,
        ),
    )
