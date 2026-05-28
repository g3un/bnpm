from __future__ import annotations

from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from bnpm.utils.python_env import resolve_bn_python_version, resolve_package_python_executable, build_uv_target_options
from tests.helpers import clear_bnpm_caches


class PythonEnvTests(unittest.TestCase):
    def setUp(self):
        clear_bnpm_caches()

    def test_python_executable_uses_bnpm_venv_python(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            python = root / "venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")

            with patch(
                "bnpm.utils.python_env.get_config",
                return_value=types.SimpleNamespace(bnpm_venv_python=python.resolve()),
            ):
                self.assertEqual(resolve_package_python_executable(), str(python.resolve()))

    def test_python_executable_reports_missing_bnpm_venv(self):
        with tempfile.TemporaryDirectory() as temp:
            python = Path(temp) / "venv" / "bin" / "python"

            with patch(
                "bnpm.utils.python_env.get_config",
                return_value=types.SimpleNamespace(bnpm_venv_python=python),
            ):
                with self.assertRaisesRegex(Exception, "BNPM Python environment is missing"):
                    resolve_package_python_executable()

    def test_uv_target_options_uses_bn_python_major_minor(self):
        with patch("bnpm.utils.python_env.find_bn_install_path", return_value=Path("BinaryNinja")), patch(
            "bnpm.utils.python_env.get_bn_python_version",
            return_value="3.12.4",
        ):
            self.assertEqual(resolve_bn_python_version(), "3.12.4")
            self.assertEqual(build_uv_target_options(), ["--python-version", "3.12"])


if __name__ == "__main__":
    unittest.main()

