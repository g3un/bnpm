from __future__ import annotations

import contextlib
import importlib
import io
import types
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from bnpm.errors import BnpmError


cli_main = importlib.import_module("bnpm.cli.main")


class CliTests(unittest.TestCase):
    def config(self):
        return types.SimpleNamespace(
            bnpm_manifest_path=Path("config/bnpm.toml"),
            bnpm_lock_path=Path("config/bnpm.lock"),
            bnpm_plugin_dir=Path("data/plugins"),
        )

    def test_setup_runs_plugin_and_venv_setup(self):
        with patch.object(cli_main, "get_config", return_value=self.config()), patch(
            "bnpm.cli.setup.setup_bn",
            return_value=Path("plugins/bnpm"),
        ) as setup_bn, patch(
            "bnpm.cli.setup.setup_bnpm_venv",
            return_value=Path("bnpm/venv"),
        ) as setup_venv:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli_main.run_cli(["setup"])

        self.assertEqual(code, 0)
        setup_bn.assert_called_once_with()
        setup_venv.assert_called_once_with()
        self.assertIn("installed BNPM Binary Ninja plugin", stdout.getvalue())
        self.assertIn("installed BNPM Python environment", stdout.getvalue())

    def test_sync_uses_config_paths(self):
        config = self.config()

        with patch.object(cli_main, "get_config", return_value=config), patch(
            "bnpm.cli.sync.sync",
            return_value=[],
        ) as sync:
            code = cli_main.run_cli(["sync"])

        self.assertEqual(code, 0)
        sync.assert_called_once_with(
            manifest_path=config.bnpm_manifest_path,
            lock_path=config.bnpm_lock_path,
            home=config.bnpm_plugin_dir,
            report_progress=ANY,
        )

    def test_verify_uses_config_paths(self):
        config = self.config()

        with patch.object(cli_main, "get_config", return_value=config), patch(
            "bnpm.cli.verify.verify_plugins",
            return_value=[],
        ) as verify:
            code = cli_main.run_cli(["verify"])

        self.assertEqual(code, 0)
        verify.assert_called_once_with(lock_path=config.bnpm_lock_path, home=config.bnpm_plugin_dir)

    def test_bnpm_error_returns_one(self):
        with patch.object(cli_main, "get_config", return_value=self.config()), patch(
            "bnpm.cli.setup.setup_bn",
            side_effect=BnpmError("failed"),
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = cli_main.run_cli(["setup"])

        self.assertEqual(code, 1)
        self.assertIn("bnpm: failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()



