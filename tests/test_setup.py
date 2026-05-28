from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, call, patch

from bnpm.helpers import find_bn_install_path, get_bn_python_version
from bnpm.setup import _run_venv_python, resolve_bn_install_api, setup_bn, setup_bnpm_venv
from tests.helpers import clear_bnpm_caches


class SetupTests(unittest.TestCase):
    def setUp(self):
        clear_bnpm_caches()

    def test_setup_installs_binaryninja_plugin_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin_dir = root / "plugins"

            target = setup_bn(plugin_dir)

            self.assertTrue(target.joinpath("__init__.py").exists())
            self.assertFalse(target.joinpath("plugin.json").exists())
            self.assertFalse(target.joinpath("requirements.txt").exists())
            self.assertFalse(target.joinpath("bnpm", "cli").exists())
            self.assertTrue(target.joinpath("bnpm", "runtime", "__init__.py").exists())

    def test_setup_replaces_existing_plugin_with_readonly_git_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin_dir = root / "plugins"
            object_path = plugin_dir / "bnpm" / ".git" / "objects" / "00" / "deadbeef"
            object_path.parent.mkdir(parents=True)
            object_path.write_text("object", encoding="utf-8")
            object_path.chmod(0o444)

            target = setup_bn(plugin_dir)

            self.assertFalse(target.joinpath(".git").exists())
            self.assertTrue(target.joinpath("bnpm", "runtime", "__init__.py").exists())

    def test_setup_reports_plugin_directory_replace_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin_dir = root / "plugins"
            plugin_dir.joinpath("bnpm").mkdir(parents=True)
            with patch("bnpm.setup.shutil.rmtree", side_effect=PermissionError("locked")):
                with self.assertRaisesRegex(Exception, "could not replace Binary Ninja plugin directory"):
                    setup_bn(plugin_dir)

    def test_setup_bnpm_venv_installs_binaryninja_api(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            install_api = root / "BinaryNinja" / "scripts" / "install_api.py"
            install_api.parent.mkdir(parents=True)
            install_api.write_text(
                """
from pathlib import Path
import sysconfig

site_packages = Path(sysconfig.get_paths()["purelib"])
site_packages.joinpath("binaryninja.py").write_text("API_VERSION = 'test'\\n", encoding="utf-8")
""".strip(),
                encoding="utf-8",
            )
            venv_path = root / "venv"

            with patch("bnpm.setup.resolve_bn_install_api", return_value=install_api), patch(
                "bnpm.setup.resolve_bn_python_major_minor",
                return_value="3.10",
            ), patch("bnpm.setup._create_venv") as create_venv, patch("bnpm.setup._run_venv_python") as run_python:
                result = setup_bnpm_venv(venv_path)

            self.assertEqual(result, venv_path.resolve())
            create_venv.assert_called_once_with(venv_path.resolve(), "3.10")
            self.assertEqual(
                run_python.call_args_list,
                [
                    call(venv_path.resolve(), [str(install_api), "--force"]),
                    call(venv_path.resolve(), ["-c", "import binaryninja"]),
                ],
            )

    def test_setup_bnpm_venv_reports_missing_install_api(self):
        with tempfile.TemporaryDirectory() as temp:
            venv_path = Path(temp) / "venv"

            with patch("bnpm.setup.resolve_bn_python_major_minor", return_value="3.10"), patch(
                "bnpm.setup._create_venv",
            ), patch("bnpm.setup.resolve_bn_install_api", return_value=None):
                with self.assertRaisesRegex(Exception, "could not find Binary Ninja scripts/install_api.py"):
                    setup_bnpm_venv(venv_path)

    def test_setup_bnpm_venv_reports_install_api_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            venv_path = root / "venv"
            install_api = root / "BinaryNinja" / "scripts" / "install_api.py"
            install_api.parent.mkdir(parents=True)
            install_api.write_text("raise SystemExit(1)\n", encoding="utf-8")

            with patch("bnpm.setup.resolve_bn_python_major_minor", return_value="3.10"), patch(
                "bnpm.setup._create_venv",
            ), patch("bnpm.setup.resolve_bn_install_api", return_value=install_api), patch(
                "bnpm.setup._run_venv_python",
                side_effect=Exception("install failed"),
            ):
                with self.assertRaisesRegex(Exception, "install failed"):
                    setup_bnpm_venv(venv_path)

    def test_run_venv_python_sets_virtual_env(self):
        with tempfile.TemporaryDirectory() as temp:
            venv_path = Path(temp) / "venv"
            python = venv_path / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")

            result = Mock(returncode=0, stdout="", stderr="")
            with patch("bnpm.setup.subprocess.run", return_value=result) as run:
                _run_venv_python(venv_path, ["script.py"])

            self.assertEqual(run.call_args.kwargs["env"]["VIRTUAL_ENV"], str(venv_path))

    def test_setup_bn_uses_bn_user_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with patch.dict(os.environ, {"BN_USER_DIRECTORY": str(root)}):
                target = setup_bn()

            self.assertEqual(target, root / "plugins" / "bnpm")

    def test_helper_finds_bn_install_path_from_lastrun(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            user_dir = root / "user"
            install_root = root / "binaryninja"
            user_dir.mkdir()
            install_root.mkdir()
            user_dir.joinpath("lastrun").write_text(str(install_root), encoding="utf-8")

            with patch("bnpm.helpers.bn.platform.system", return_value="Linux"), patch.dict(
                os.environ,
                {"BN_USER_DIRECTORY": str(user_dir)},
            ):
                self.assertEqual(find_bn_install_path(), install_root)

    def test_helper_finds_bn_install_path_from_lastrun_linux_executable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            user_dir = root / "user"
            install_root = root / "binaryninja"
            binary = install_root / "binaryninja"
            user_dir.mkdir()
            install_root.mkdir()
            binary.write_text("", encoding="utf-8")
            user_dir.joinpath("lastrun").write_text(str(binary), encoding="utf-8")

            with patch("bnpm.helpers.bn.platform.system", return_value="Linux"), patch.dict(
                os.environ,
                {"BN_USER_DIRECTORY": str(user_dir)},
            ):
                self.assertEqual(find_bn_install_path(), install_root)

    def test_helper_finds_bn_install_path_from_lastrun_windows_executable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            user_dir = root / "user"
            install_root = root / "BinaryNinja"
            binary = install_root / "binaryninja.exe"
            user_dir.mkdir()
            install_root.mkdir()
            binary.write_text("", encoding="utf-8")
            user_dir.joinpath("lastrun").write_text(str(binary), encoding="utf-8")

            with patch("bnpm.helpers.bn.platform.system", return_value="Windows"), patch.dict(
                os.environ,
                {"BN_USER_DIRECTORY": str(user_dir)},
            ):
                self.assertEqual(find_bn_install_path(), install_root)

    def test_helper_returns_none_without_lastrun(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            user_dir = root / "user"
            user_dir.mkdir()

            with patch("bnpm.helpers.bn.platform.system", return_value="Linux"), patch.dict(
                os.environ,
                {"BN_USER_DIRECTORY": str(user_dir)},
            ):
                self.assertIsNone(find_bn_install_path())

    def test_helper_finds_macos_app_root_from_lastrun_macos_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            user_dir = root / "user"
            install_root = root / "Binary Ninja.app"
            macos_dir = install_root / "Contents" / "MacOS"
            user_dir.mkdir()
            macos_dir.mkdir(parents=True)
            user_dir.joinpath("lastrun").write_text(str(macos_dir), encoding="utf-8")

            with patch("bnpm.helpers.bn.platform.system", return_value="Darwin"), patch.dict(
                os.environ,
                {"BN_USER_DIRECTORY": str(user_dir)},
            ):
                self.assertEqual(find_bn_install_path(), install_root)

    def test_helper_reads_bn_bundled_python_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            python = root / "plugins" / "python" / "python.exe"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")
            result = Mock(returncode=0, stdout='Python version: "3.10"\n', stderr="")

            with patch("bnpm.helpers.bn.platform.system", return_value="Windows"), patch(
                "bnpm.helpers.bn.subprocess.run",
                return_value=result,
            ) as run:
                self.assertEqual(get_bn_python_version(root), "3.10")

            self.assertEqual(run.call_args.args[0], [str(python.resolve()), "-m", "sysconfig"])

    def test_helper_reads_macos_bnpython_version_from_sysconfig(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            python = root / "Binary Ninja.app" / "Contents" / "MacOS" / "bnpython3"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")
            sysconfig = Mock(returncode=0, stdout='Python version: "3.10"\n', stderr="")

            with patch("bnpm.helpers.bn.platform.system", return_value="Darwin"), patch(
                "bnpm.helpers.bn.subprocess.run",
                return_value=sysconfig,
            ) as run:
                self.assertEqual(get_bn_python_version(root / "Binary Ninja.app"), "3.10")

            self.assertEqual(run.call_args.args[0], [str(python.resolve()), "-m", "sysconfig"])

    def test_helper_reads_linux_bnpython_version_from_sysconfig(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            python = root / "binaryninja" / "bnpython3"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")
            sysconfig = Mock(returncode=0, stdout='Python version: "3.10"\n', stderr="")

            with patch("bnpm.helpers.bn.platform.system", return_value="Linux"), patch(
                "bnpm.helpers.bn.subprocess.run",
                return_value=sysconfig,
            ) as run:
                self.assertEqual(get_bn_python_version(root / "binaryninja"), "3.10")

            self.assertEqual(run.call_args.args[0], [str(python.resolve()), "-m", "sysconfig"])

    def test_helper_returns_none_when_bn_python_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()

            with patch("bnpm.helpers.bn.platform.system", return_value="Windows"):
                self.assertIsNone(get_bn_python_version(root))

    def test_resolve_bn_install_api_finds_macos_bundle_script(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            install_root = root / "Binary Ninja.app"
            install_api = install_root / "Contents" / "Resources" / "scripts" / "install_api.py"
            install_api.parent.mkdir(parents=True)
            install_api.write_text("", encoding="utf-8")

            with patch("bnpm.setup.find_bn_install_path", return_value=install_root):
                self.assertEqual(resolve_bn_install_api(), install_api)
