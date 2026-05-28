from __future__ import annotations

import os
import contextlib
import io
import sys
import tempfile
import types
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from bnpm.lockfile import LockedPackage, load_lockfile
from bnpm.packages import _install_requirements, install_packages
from bnpm.sync import sync
from bnpm.cli.add import run as add_run
from bnpm.utils.locations import (
    resolve_package_dir,
    convert_path_to_file_uri,
)
from tests.helpers import clear_bnpm_caches

class PackagesTests(unittest.TestCase):
    def setUp(self):
        clear_bnpm_caches()

    def test_add_path_locks_resolved_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            plugin.mkdir()
            plugin.joinpath("__init__.py").write_text("", encoding="utf-8")
            plugin.joinpath("requirements.txt").write_text(
                """
# ignored comment
tomli>=1.1; python_version < '3.11'

requests>=2.31,<3
""".strip(),
                encoding="utf-8",
            )
            manifest = root / "bnpm.toml"

            with patch(
                "bnpm.sync.install_packages",
                return_value=[
                    LockedPackage(
                        name="requests",
                        source="pypi",
                        version="pypi:2.32.3",
                        dependencies=["urllib3<3,>=1.21.1"],
                    ),
                    LockedPackage(
                        name="tomli",
                        source="pypi",
                        version="pypi:2.4.1",
                    ),
                    LockedPackage(
                        name="urllib3",
                        source="pypi",
                        version="pypi:2.5.0",
                    ),
                ],
            ):
                code = add_run(
                    "local",
                    None,
                    str(plugin),
                    None,
                    None,
                    None,
                    manifest,
                    root / "bnpm.lock",
                    root / "home",
                )

            self.assertEqual(code, 0)
            lockfile = load_lockfile(root / "bnpm.lock")
            self.assertEqual(lockfile.plugins[0].dependencies, ["requests==2.32.3", "tomli==2.4.1"])
            packages = {package.name: package for package in lockfile.packages}
            self.assertEqual(packages["requests"].dependencies, ["urllib3==2.5.0"])

    def test_sync_writes_installed_package_versions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            plugin.mkdir()
            plugin.joinpath("__init__.py").write_text("", encoding="utf-8")
            plugin.joinpath("requirements.txt").write_text("requests>=2.31,<3\n", encoding="utf-8")
            manifest = root / "bnpm.toml"
            manifest.write_text(
                f"""
version = 1

[plugins]
local = {{ path = "{str(plugin).replace(chr(92), chr(92) * 2)}" }}
""".strip(),
                encoding="utf-8",
            )

            with patch(
                "bnpm.sync.install_packages",
                return_value=[
                    LockedPackage(
                        name="requests",
                        source="pypi+https://files.pythonhosted.org/packages/requests.whl",
                        version="pypi:2.32.3",
                        checksum="sha256:cafebabe",
                        dependencies=["urllib3<3,>=1.21.1"],
                    ),
                    LockedPackage(
                        name="urllib3",
                        source="pypi",
                        version="pypi:2.5.0",
                    )
                ],
            ) as install_packages:
                sync(manifest_path=manifest, lock_path=root / "bnpm.lock", home=root / "home")
                code = 0

            lockfile = load_lockfile(root / "bnpm.lock")
            self.assertEqual(code, 0)
            install_packages.assert_called_once()
            self.assertEqual(install_packages.call_args.args, (["requests>=2.31,<3"], (root / "home").resolve()))
            self.assertEqual(lockfile.plugins[0].dependencies, ["requests==2.32.3"])
            self.assertEqual(lockfile.packages[0].name, "requests")
            self.assertEqual(lockfile.packages[0].version, "pypi:2.32.3")

    def test_pyproject_dependencies_override_collect_requirements_txt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            plugin.mkdir()
            plugin.joinpath("__init__.py").write_text("", encoding="utf-8")
            plugin.joinpath("pyproject.toml").write_text(
                """
[project]
name = "sample-plugin"
dependencies = ["requests>=2.31,<3"]
""".strip(),
                encoding="utf-8",
            )
            plugin.joinpath("requirements.txt").write_text("tomli>=1.1\n", encoding="utf-8")
            manifest = root / "bnpm.toml"
            manifest.write_text(
                f"""
version = 1

[plugins]
local = {{ path = "{str(plugin).replace(chr(92), chr(92) * 2)}" }}
""".strip(),
                encoding="utf-8",
            )

            with patch(
                "bnpm.sync.install_packages",
                return_value=[
                    LockedPackage(name="requests", source="pypi", version="pypi:2.32.3"),
                    LockedPackage(name="tomli", source="pypi", version="pypi:2.4.1"),
                ],
            ) as install_packages:
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    sync(
                        manifest_path=manifest,
                        lock_path=root / "bnpm.lock",
                        home=root / "home",
                        report_progress=lambda message: print(message, file=sys.stderr),
                    )
                    code = 0

            lockfile = load_lockfile(root / "bnpm.lock")
            self.assertEqual(code, 0)
            self.assertIn("requirements.txt", err.getvalue())
            install_packages.assert_called_once()
            self.assertEqual(install_packages.call_args.args, (["requests>=2.31,<3"], (root / "home").resolve()))
            self.assertEqual(lockfile.plugins[0].dependencies, ["requests==2.32.3"])
            self.assertNotIn("tomli==2.4.1", lockfile.plugins[0].dependencies or [])

    def test_package_install_uses_uv_target_first(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requirements_path = root / "requirements.txt"
            target = root / "packages"
            requirements_path.write_text("requests\n", encoding="utf-8")
            run = Mock(return_value=types.SimpleNamespace(returncode=0, stdout="", stderr=""))

            with patch("bnpm.packages.subprocess.run", run), patch(
                "bnpm.packages.build_uv_target_options",
                return_value=["--python-version", "3.10"],
            ):
                _install_requirements(requirements_path, target)

            self.assertEqual(run.call_count, 1)
            args = run.call_args.args[0]
            self.assertEqual(args[:3], ["uv", "pip", "install"])
            self.assertIn("--python-version", args)
            self.assertEqual(args[args.index("--python-version") + 1], "3.10")
            self.assertNotIn("--python-platform", args)
            self.assertIn("--target", args)
            self.assertEqual(args[args.index("--target") + 1], str(target))
            self.assertIn(str(requirements_path), args)

    def test_package_install_falls_back_to_pip_when_uv_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requirements_path = root / "requirements.txt"
            target = root / "packages"
            requirements_path.write_text("requests\n", encoding="utf-8")
            run = Mock(
                side_effect=[
                    FileNotFoundError(),
                    types.SimpleNamespace(returncode=0, stdout="", stderr=""),
                ]
            )

            python = root / "venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")

            with patch("bnpm.packages.subprocess.run", run), patch(
                "bnpm.utils.python_env.get_config",
                return_value=types.SimpleNamespace(bnpm_venv_python=python),
            ):
                _install_requirements(requirements_path, target)

            self.assertEqual(run.call_count, 2)
            args = run.call_args.args[0]
            self.assertEqual(args[0], str(python))
            self.assertEqual(args[1:5], ["-m", "pip", "--isolated", "install"])
            self.assertIn("--target", args)
            self.assertEqual(args[args.index("--target") + 1], str(target))

    def test_package_install_falls_back_to_pip_when_uv_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requirements_path = root / "requirements.txt"
            target = root / "packages"
            requirements_path.write_text("requests\n", encoding="utf-8")
            run = Mock(
                side_effect=[
                    types.SimpleNamespace(returncode=1, stdout="", stderr="uv failed"),
                    types.SimpleNamespace(returncode=0, stdout="", stderr=""),
                ]
            )
            python = root / "venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")

            with patch("bnpm.packages.subprocess.run", run), patch(
                "bnpm.utils.python_env.get_config",
                return_value=types.SimpleNamespace(bnpm_venv_python=python),
            ):
                _install_requirements(requirements_path, target)

            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args[0][0], str(python))

    def test_package_install_bootstraps_pip_when_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requirements_path = root / "requirements.txt"
            target = root / "packages"
            requirements_path.write_text("requests\n", encoding="utf-8")
            run = Mock(
                side_effect=[
                    FileNotFoundError(),
                    types.SimpleNamespace(returncode=1, stdout="", stderr="No module named pip"),
                    types.SimpleNamespace(returncode=0, stdout="", stderr=""),
                    types.SimpleNamespace(returncode=0, stdout="", stderr=""),
                ]
            )
            python = root / "venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")

            with patch("bnpm.packages.subprocess.run", run), patch(
                "bnpm.utils.python_env.get_config",
                return_value=types.SimpleNamespace(bnpm_venv_python=python),
            ):
                _install_requirements(requirements_path, target)

            self.assertEqual(run.call_args_list[2].args[0], [str(python), "-m", "ensurepip", "--upgrade"])

    def test_package_install_reports_pip_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requirements_path = root / "requirements.txt"
            target = root / "packages"
            requirements_path.write_text("requests\n", encoding="utf-8")
            run = Mock(
                side_effect=[
                    FileNotFoundError(),
                    types.SimpleNamespace(returncode=1, stdout="", stderr="pip failed"),
                ]
            )
            python = root / "venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")

            with patch("bnpm.packages.subprocess.run", run), patch(
                "bnpm.utils.python_env.get_config",
                return_value=types.SimpleNamespace(bnpm_venv_python=python),
            ):
                with self.assertRaisesRegex(Exception, "pip failed"):
                    _install_requirements(requirements_path, target)

    def test_install_packages_creates_empty_package_dir_without_requirements(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "plugins"

            packages = install_packages([], home)

            self.assertEqual(packages, [])
            self.assertTrue(resolve_package_dir(home).exists())

    def test_sync_resolves_relative_path_from_manifest_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "config"
            plugin = root / "plugin"
            cwd = root / "cwd"
            config.mkdir()
            plugin.mkdir()
            cwd.mkdir()
            plugin.joinpath("__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            manifest = config / "bnpm.toml"
            manifest.write_text(
                """
version = 1

[plugins]
local = { path = "../plugin" }
""".strip(),
                encoding="utf-8",
            )
            old_cwd = Path.cwd()
            try:
                os.chdir(cwd)

                sync(manifest_path=manifest, lock_path=config / "bnpm.lock", home=root / "home")
                code = 0
            finally:
                os.chdir(old_cwd)

            locked = load_lockfile(config / "bnpm.lock").plugins
            self.assertEqual(code, 0)
            self.assertEqual(len(locked), 1)
            self.assertEqual(locked[0].source, convert_path_to_file_uri(plugin))








