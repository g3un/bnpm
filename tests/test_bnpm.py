from __future__ import annotations

import importlib.util
import os
import contextlib
import io
import sys
import tempfile
import types
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from bnpm.bundle import build_bundle
from bnpm.cli import main
from bnpm.lockfile import LockedPackage, LockedPlugin, load_lockfile, write_lockfile
from bnpm.manifest import load_manifest
from bnpm.packages import _install_requirements
from bnpm.runtime import activate
from bnpm.setup import default_binaryninja_plugin_dir
from bnpm.source import SourceSpec, parse_plugin
from bnpm.status import load_manifest_plugins, lock_mismatches
from bnpm.store import (
    default_config_dir,
    default_home,
    default_manifest_path,
    file_uri_to_path,
    install_dir,
    package_dir,
    plugin_dir,
    path_to_file_uri,
)
from bnpm.toml_compat import _parse_subset


class SourceTests(unittest.TestCase):
    def test_github_shorthand(self):
        spec = parse_plugin("hexpatch", "github.com/user/hexpatch")

        self.assertEqual(spec.name, "hexpatch")
        self.assertEqual(spec.kind, "git")
        self.assertEqual(spec.git, "https://github.com/user/hexpatch.git")
        self.assertEqual(spec.version, "HEAD")

    def test_git_table_with_rev(self):
        spec = parse_plugin(
            "hexpatch",
            {"git": "https://github.com/user/hexpatch.git", "rev": "abc123"},
        )

        self.assertEqual(spec.version, "rev:abc123")

    def test_git_without_ref_uses_head_version(self):
        spec = parse_plugin("hexpatch", "github.com/user/hexpatch")

        self.assertEqual(spec.version, "HEAD")

    def test_query_string_refs_are_not_supported(self):
        with self.assertRaisesRegex(Exception, "query strings are not supported"):
            parse_plugin("hexpatch", "github.com/user/hexpatch?branch=main")

    def test_inline_refs_are_not_supported(self):
        with self.assertRaisesRegex(Exception, "inline refs are not supported"):
            parse_plugin("hexpatch", "github.com/user/hexpatch@v1.2.3")

    def test_ssh_shorthand_does_not_treat_at_as_tag(self):
        spec = parse_plugin("hexpatch", "git@github.com:user/hexpatch.git")

        self.assertEqual(spec.git, "git@github.com:user/hexpatch.git")
        self.assertEqual(spec.version, "HEAD")


class ManifestTests(unittest.TestCase):
    def test_load_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bnpm.toml"
            path.write_text(
                """
version = 1

[plugins]
hexpatch = { git = "https://github.com/user/hexpatch.git", tag = "v1.2.3" }
""".strip(),
                encoding="utf-8",
            )

            manifest = load_manifest(path)

        self.assertEqual(manifest.version, 1)
        self.assertIn("hexpatch", manifest.plugins)

    def test_toml_subset_parser_supports_manifest_shape(self):
        data = _parse_subset(
            """
version = 1

[plugins]
hexpatch = { git = "https://github.com/user/hexpatch.git", tag = "v1.2.3" }
devtools = { git = "https://github.com/user/devtools.git", branch = "main" }
""".strip()
        )

        self.assertEqual(data["version"], 1)
        self.assertEqual(data["plugins"]["devtools"]["branch"], "main")

    def test_toml_subset_parser_supports_pyproject_shape(self):
        data = _parse_subset(
            """
[project]
name = "sample-plugin"
dependencies = ["requests>=2.31,<3"]

[tool.bnpm]
package = "actual_package"
source = "src"
""".strip()
        )

        self.assertEqual(data["project"]["name"], "sample-plugin")
        self.assertEqual(data["project"]["dependencies"], ["requests>=2.31,<3"])
        self.assertEqual(data["tool"]["bnpm"]["package"], "actual_package")
        self.assertEqual(data["tool"]["bnpm"]["source"], "src")


class LockfileTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bnpm.lock"
            write_lockfile(
                path,
                [
                    LockedPlugin(
                        name="hexpatch",
                        source="https://github.com/user/hexpatch.git",
                        version="tag:v1.2.3",
                        checksum="sha256:deadbeef",
                        commit="abc123",
                        dependencies=["requests==2.32.3"],
                    )
                ],
                [
                    LockedPackage(
                        name="requests",
                        source="pypi+https://files.pythonhosted.org/packages/requests.whl",
                        version="pypi:2.32.3",
                        checksum="sha256:cafebabe",
                        dependencies=["urllib3==2.5.0"],
                    )
                ],
            )
            lockfile = load_lockfile(path)

        self.assertEqual(lockfile.plugins[0].name, "hexpatch")
        self.assertEqual(lockfile.plugins[0].version, "tag:v1.2.3")
        self.assertEqual(lockfile.plugins[0].commit, "abc123")
        self.assertEqual(lockfile.plugins[0].dependencies, ["requests==2.32.3"])
        self.assertEqual(lockfile.packages[0].name, "requests")
        self.assertEqual(lockfile.packages[0].version, "pypi:2.32.3")
        self.assertEqual(lockfile.packages[0].checksum, "sha256:cafebabe")
        self.assertEqual(lockfile.packages[0].dependencies, ["urllib3==2.5.0"])

    def test_load_lockfile_defaults_missing_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bnpm.lock"
            path.write_text(
                """
version = 1

[[plugins]]
name = "hexpatch"
source = "https://github.com/user/hexpatch.git"
checksum = "sha256:deadbeef"
""".strip(),
                encoding="utf-8",
            )

            lockfile = load_lockfile(path)

        self.assertEqual(lockfile.plugins[0].dependencies, [])
        self.assertEqual(lockfile.packages, [])

    def test_write_lockfile_does_not_leave_temp_files(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bnpm.lock"
            write_lockfile(
                path,
                [
                    LockedPlugin(
                        name="hexpatch",
                        source="https://github.com/user/hexpatch.git",
                        version="HEAD",
                        checksum="sha256:deadbeef",
                        commit="abc123",
                    )
                ],
            )

            temp_files = list(Path(temp).glob(".bnpm.lock.*.tmp"))

        self.assertEqual(temp_files, [])

    def test_manifest_lock_mismatch_detects_missing_plugin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            plugin.mkdir()
            manifest = root / "bnpm.toml"
            manifest.write_text(
                """
version = 1

[plugins]
local = { path = "plugin" }
""".strip(),
                encoding="utf-8",
            )
            lock = root / "bnpm.lock"
            write_lockfile(lock, [])

            manifest_plugins = load_manifest_plugins(manifest)
            mismatches = lock_mismatches(manifest_plugins, load_lockfile(lock))

        self.assertEqual(mismatches, ["plugin 'local' is in bnpm.toml but not bnpm.lock"])

    def test_manifest_lock_mismatch_detects_source_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            manifest = root / "bnpm.toml"
            manifest.write_text(
                """
version = 1

[plugins]
local = { path = "second" }
""".strip(),
                encoding="utf-8",
            )
            lock = root / "bnpm.lock"
            write_lockfile(
                lock,
                [
                    LockedPlugin(
                        name="local",
                        source=first.resolve().as_uri(),
                        checksum="sha256:deadbeef",
                    )
                ],
            )

            manifest_plugins = load_manifest_plugins(manifest)
            mismatches = lock_mismatches(manifest_plugins, load_lockfile(lock))

        self.assertEqual(mismatches, ["plugin 'local' source changed"])


class CliRuntimeTests(unittest.TestCase):
    def test_add_path_writes_absolute_path_and_syncs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            plugin.mkdir()
            plugin.joinpath("__init__.py").write_text("", encoding="utf-8")
            manifest = root / "bnpm.toml"

            with patch("bnpm.sync.install_packages", return_value=[]):
                code = main(
                    [
                        "--manifest-path",
                        str(manifest),
                        "--home",
                        str(root / "home"),
                        "add",
                        "local",
                        "--path",
                        str(plugin),
                    ]
                )

            self.assertEqual(code, 0)
            escaped_path = str(plugin.resolve()).replace("\\", "\\\\")
            self.assertIn(
                f'path = "{escaped_path}"',
                manifest.read_text(encoding="utf-8"),
            )
            lockfile = load_lockfile(root / "bnpm.lock")
            self.assertEqual(lockfile.plugins[0].name, "local")

    def test_setup_installs_binaryninja_plugin_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin_dir = root / "plugins"

            code = main(["setup", "--plugin-dir", str(plugin_dir)])

            target = plugin_dir / "bnpm"
            self.assertEqual(code, 0)
            self.assertTrue(target.joinpath("__init__.py").exists())
            self.assertFalse(target.joinpath("plugin.json").exists())
            self.assertFalse(target.joinpath("requirements.txt").exists())
            self.assertTrue(target.joinpath("bnpm", "runtime.py").exists())

    def test_default_binaryninja_plugin_dir_uses_override(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with patch.dict(os.environ, {"BNPM_BINARYNINJA_PLUGIN_DIR": str(root)}):
                self.assertEqual(default_binaryninja_plugin_dir(), root)

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
                code = main(
                    [
                        "--manifest-path",
                        str(manifest),
                        "--home",
                        str(root / "home"),
                        "add",
                        "local",
                        "--path",
                        str(plugin),
                    ]
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
                code = main(["--manifest-path", str(manifest), "--home", str(root / "home"), "sync"])

            lockfile = load_lockfile(root / "bnpm.lock")
            self.assertEqual(code, 0)
            install_packages.assert_called_once()
            self.assertEqual(install_packages.call_args.args, (["requests>=2.31,<3"], (root / "home").resolve()))
            self.assertEqual(lockfile.plugins[0].dependencies, ["requests==2.32.3"])
            self.assertEqual(lockfile.packages[0].name, "requests")
            self.assertEqual(lockfile.packages[0].version, "pypi:2.32.3")

    def test_pyproject_dependencies_override_requirements_txt(self):
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
                    code = main(["--manifest-path", str(manifest), "--home", str(root / "home"), "sync"])

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
            requirements = root / "requirements.txt"
            target = root / "packages"
            requirements.write_text("requests\n", encoding="utf-8")
            run = Mock(return_value=types.SimpleNamespace(returncode=0, stdout="", stderr=""))

            with patch("bnpm.packages.subprocess.run", run):
                _install_requirements(requirements, target)

            self.assertEqual(run.call_count, 1)
            args = run.call_args.args[0]
            self.assertEqual(args[:3], ["uv", "pip", "install"])
            self.assertIn("--target", args)
            self.assertEqual(args[args.index("--target") + 1], str(target))
            self.assertIn(str(requirements), args)

    def test_package_install_falls_back_to_pip_when_uv_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requirements = root / "requirements.txt"
            target = root / "packages"
            requirements.write_text("requests\n", encoding="utf-8")
            run = Mock(
                side_effect=[
                    FileNotFoundError(),
                    types.SimpleNamespace(returncode=0, stdout="", stderr=""),
                ]
            )

            with patch("bnpm.packages.subprocess.run", run), patch(
                "bnpm.packages.shutil.which",
                side_effect=lambda name: "/usr/bin/python3" if name == "python3" else None,
            ), patch("bnpm.packages.sys.prefix", str(root / "missing-prefix")):
                _install_requirements(requirements, target)

            self.assertEqual(run.call_count, 2)
            args = run.call_args.args[0]
            self.assertEqual(args[0], "/usr/bin/python3")
            self.assertEqual(args[1:5], ["-m", "pip", "--isolated", "install"])
            self.assertIn("--target", args)
            self.assertEqual(args[args.index("--target") + 1], str(target))

    def test_add_path_treats_it_as_path_plugin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            plugin.mkdir()
            plugin.joinpath("__init__.py").write_text("", encoding="utf-8")
            manifest = root / "bnpm.toml"

            code = main(
                [
                    "--manifest-path",
                    str(manifest),
                    "--home",
                    str(root / "home"),
                    "add",
                    "local",
                    "--path",
                    str(plugin),
                ]
            )

            self.assertEqual(code, 0)
            self.assertEqual(load_manifest(manifest).plugins["local"].kind, "path")
            self.assertEqual(load_lockfile(root / "bnpm.lock").plugins[0].source, plugin.resolve().as_uri())

    def test_add_git_plugin_accepts_branch_option(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "bnpm.toml"

            def fake_install(spec, home, progress=None):
                return LockedPlugin(
                    name=spec.name,
                    source=spec.git,
                    version=spec.version,
                    checksum="sha256:fake",
                    commit="abc123",
                )

            with patch("bnpm.sync.install", side_effect=fake_install):
                code = main(
                    [
                        "--manifest-path",
                        str(manifest),
                        "--home",
                        str(root / "home"),
                        "add",
                        "devtools",
                        "--git",
                        "github.com/user/devtools",
                        "--branch",
                        "main",
                    ]
                )

            spec = load_manifest(manifest).plugins["devtools"]
            locked = load_lockfile(root / "bnpm.lock").plugins[0]
            self.assertEqual(code, 0)
            self.assertEqual(spec.branch, "main")
            self.assertEqual(locked.version, "branch:main")

    def test_add_local_path_rejects_ref_options(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            plugin.mkdir()
            manifest = root / "bnpm.toml"

            code = main(
                [
                    "--manifest-path",
                    str(manifest),
                    "--home",
                    str(root / "home"),
                    "add",
                    "local",
                    "--path",
                    str(plugin),
                    "--branch",
                    "main",
                ]
            )

            self.assertEqual(code, 1)

    def test_add_requires_explicit_source_kind(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(
                    [
                        "--manifest-path",
                        str(root / "bnpm.toml"),
                        "--home",
                        str(root / "home"),
                        "add",
                        "plugin",
                        "github.com/user/plugin",
                    ]
                )

    def test_add_rejects_multiple_source_kinds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(
                    [
                        "--manifest-path",
                        str(root / "bnpm.toml"),
                        "--home",
                        str(root / "home"),
                        "add",
                        "plugin",
                        "--git",
                        "github.com/user/plugin",
                        "--path",
                        "plugin",
                    ]
                )

    def test_remove_updates_manifest_and_syncs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            plugin.mkdir()
            plugin.joinpath("__init__.py").write_text("", encoding="utf-8")
            manifest = root / "bnpm.toml"
            manifest.write_text(
                f"""
version = 1

[plugins]
local = {{ path = "{str(plugin).replace(chr(92), chr(92) * 2)}" }}
""".strip(),
                encoding="utf-8",
            )
            self.assertEqual(main(["--manifest-path", str(manifest), "--home", str(root / "home"), "sync"]), 0)

            code = main(["--manifest-path", str(manifest), "--home", str(root / "home"), "remove", "local"])

            self.assertEqual(code, 0)
            self.assertEqual(load_manifest(manifest).plugins, {})
            self.assertEqual(load_lockfile(root / "bnpm.lock").plugins, [])

    def test_remove_deletes_plugin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            packages = package_dir(home)
            packages.mkdir(parents=True)
            source = "https://github.com/user/plugin.git"
            commit = "abc123"
            plugin = plugin_dir(home, source, commit)
            plugin.mkdir(parents=True)
            plugin.joinpath("__init__.py").write_text("", encoding="utf-8")
            manifest = root / "bnpm.toml"
            manifest.write_text(
                """
version = 1

[plugins]
plugin = { git = "https://github.com/user/plugin.git" }
""".strip(),
                encoding="utf-8",
            )
            write_lockfile(
                root / "bnpm.lock",
                [
                    LockedPlugin(
                        name="plugin",
                        source=source,
                        version="HEAD",
                        commit=commit,
                        checksum="sha256:deadbeef",
                    )
                ],
            )

            code = main(["--manifest-path", str(manifest), "--home", str(home), "remove", "plugin"])

            self.assertEqual(code, 0)
            self.assertFalse(plugin.exists())
            self.assertTrue(packages.exists())
            self.assertEqual(load_lockfile(root / "bnpm.lock").plugins, [])

    def test_update_refreshes_selected_plugin_lock_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            first.joinpath("__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            second.joinpath("__init__.py").write_text("VALUE = 2\n", encoding="utf-8")
            manifest = root / "bnpm.toml"
            manifest.write_text(
                f"""
version = 1

[plugins]
first = {{ path = "{str(first).replace(chr(92), chr(92) * 2)}" }}
second = {{ path = "{str(second).replace(chr(92), chr(92) * 2)}" }}
""".strip(),
                encoding="utf-8",
            )
            self.assertEqual(main(["--manifest-path", str(manifest), "--home", str(root / "home"), "sync"]), 0)
            before = {plugin.name: plugin.checksum for plugin in load_lockfile(root / "bnpm.lock").plugins}
            first.joinpath("__init__.py").write_text("VALUE = 10\n", encoding="utf-8")
            second.joinpath("__init__.py").write_text("VALUE = 20\n", encoding="utf-8")

            code = main(["--manifest-path", str(manifest), "--home", str(root / "home"), "update", "first"])

            after = {plugin.name: plugin.checksum for plugin in load_lockfile(root / "bnpm.lock").plugins}
            self.assertEqual(code, 0)
            self.assertNotEqual(after["first"], before["first"])
            self.assertEqual(after["second"], before["second"])

    def test_update_rejects_unknown_plugin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "bnpm.toml"
            manifest.write_text(
                """
version = 1

[plugins]
""".strip(),
                encoding="utf-8",
            )
            self.assertEqual(main(["--manifest-path", str(manifest), "--home", str(root / "home"), "sync"]), 0)

            code = main(["--manifest-path", str(manifest), "--home", str(root / "home"), "update", "missing"])

            self.assertEqual(code, 1)

    def test_add_requires_sync_when_manifest_and_lock_differ(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            plugin.mkdir()
            manifest = root / "bnpm.toml"
            manifest.write_text(
                """
version = 1

[plugins]
stale = { path = "plugin" }
""".strip(),
                encoding="utf-8",
            )

            code = main(
                [
                    "--manifest-path",
                    str(manifest),
                    "--home",
                    str(root / "home"),
                    "add",
                    "local",
                    "--path",
                    str(plugin),
                ]
            )

            self.assertEqual(code, 1)

    def test_path_plugin_sync_and_runtime_load(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            plugin.mkdir()
            marker = root / "loaded.txt"
            plugin.joinpath("helper.py").write_text(
                "VALUE = 'ok'\n",
                encoding="utf-8",
            )
            plugin.joinpath("__init__.py").write_text(
                f"from pathlib import Path\nfrom .helper import VALUE\nPath({str(marker)!r}).write_text(VALUE, encoding='utf-8')\n",
                encoding="utf-8",
            )
            manifest = root / "bnpm.toml"
            manifest.write_text(
                """
version = 1

[plugins]
pyproject_src = { path = "plugin" }
""".strip(),
                encoding="utf-8",
            )

            code = main(["--manifest-path", str(manifest), "--home", str(root / "home"), "sync"])
            self.assertEqual(code, 0)
            lockfile = load_lockfile(root / "bnpm.lock")
            self.assertEqual(lockfile.plugins[0].source, plugin.resolve().as_uri())
            self.assertIsNone(lockfile.plugins[0].version)
            self.assertIsNone(lockfile.plugins[0].commit)

            activate(lock_path=root / "bnpm.lock", home=root / "home")

            self.assertEqual(marker.read_text(encoding="utf-8"), "ok")

    def test_pyproject_src_layout_runtime_load(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            package = plugin / "src" / "sample_plugin"
            package.mkdir(parents=True)
            marker = root / "loaded.txt"
            plugin.joinpath("pyproject.toml").write_text(
                """
[project]
name = "sample-plugin"
dependencies = []
""".strip(),
                encoding="utf-8",
            )
            package.joinpath("helper.py").write_text("VALUE = 'ok'\n", encoding="utf-8")
            package.joinpath("__init__.py").write_text(
                f"from pathlib import Path\nfrom .helper import VALUE\nPath({str(marker)!r}).write_text(VALUE, encoding='utf-8')\n",
                encoding="utf-8",
            )
            manifest = root / "bnpm.toml"
            manifest.write_text(
                """
version = 1

[plugins]
local = { path = "plugin" }
""".strip(),
                encoding="utf-8",
            )

            code = main(["--manifest-path", str(manifest), "--home", str(root / "home"), "sync"])
            self.assertEqual(code, 0)

            activate(lock_path=root / "bnpm.lock", home=root / "home")

            self.assertEqual(marker.read_text(encoding="utf-8"), "ok")

    def test_tool_bnpm_runtime_entry_overrides_project_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            package = plugin / "source" / "actual_package"
            package.mkdir(parents=True)
            marker = root / "loaded.txt"
            plugin.joinpath("pyproject.toml").write_text(
                """
[project]
name = "different-name"
dependencies = []

[tool.bnpm]
package = "actual_package"
source = "source"
""".strip(),
                encoding="utf-8",
            )
            package.joinpath("helper.py").write_text("VALUE = 'ok'\n", encoding="utf-8")
            package.joinpath("__init__.py").write_text(
                f"from pathlib import Path\nfrom .helper import VALUE\nPath({str(marker)!r}).write_text(VALUE, encoding='utf-8')\n",
                encoding="utf-8",
            )
            manifest = root / "bnpm.toml"
            manifest.write_text(
                """
version = 1

[plugins]
tool_bnpm = { path = "plugin" }
""".strip(),
                encoding="utf-8",
            )

            code = main(["--manifest-path", str(manifest), "--home", str(root / "home"), "sync"])
            self.assertEqual(code, 0)

            activate(lock_path=root / "bnpm.lock", home=root / "home")

            self.assertEqual(marker.read_text(encoding="utf-8"), "ok")

    def test_git_plugin_checksum_mismatch_skips_runtime_load(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            source = "https://github.com/user/plugin.git"
            commit = "abc123"
            plugin = plugin_dir(home, source, commit)
            plugin.mkdir(parents=True)
            marker = root / "loaded.txt"
            plugin.joinpath("__init__.py").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad', encoding='utf-8')\n",
                encoding="utf-8",
            )
            lock = root / "bnpm.lock"
            write_lockfile(
                lock,
                [
                    LockedPlugin(
                        name="bad",
                        source=source,
                        version="HEAD",
                        checksum="sha256:not-the-real-hash",
                        commit=commit,
                    )
                ],
            )

            activate(lock_path=lock, home=home)

            self.assertFalse(marker.exists())

    def test_path_plugin_checksum_mismatch_warns_and_loads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / "plugin"
            plugin.mkdir()
            marker = root / "loaded.txt"
            plugin.joinpath("__init__.py").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('ok', encoding='utf-8')\n",
                encoding="utf-8",
            )
            lock = root / "bnpm.lock"
            write_lockfile(
                lock,
                [
                    LockedPlugin(
                        name="local-mismatch",
                        source=plugin.resolve().as_uri(),
                        checksum="sha256:not-the-real-hash",
                    )
                ],
            )

            activate(lock_path=lock, home=root / "home")

            self.assertEqual(marker.read_text(encoding="utf-8"), "ok")

    def test_default_paths_use_bnpm_config_and_data_dirs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            old_config = os.environ.get("BNPM_CONFIG_DIR")
            old_data = os.environ.get("BNPM_DATA_DIR")
            try:
                os.environ["BNPM_CONFIG_DIR"] = str(root / "config")
                os.environ["BNPM_DATA_DIR"] = str(root / "data")

                self.assertEqual(default_config_dir(), root / "config")
                self.assertEqual(default_manifest_path(), root / "config" / "bnpm.toml")
                self.assertEqual(default_home(), root / "data" / "plugins")
                self.assertEqual(package_dir(default_home()), root / "data" / "packages")
            finally:
                if old_config is None:
                    os.environ.pop("BNPM_CONFIG_DIR", None)
                else:
                    os.environ["BNPM_CONFIG_DIR"] = old_config
                if old_data is None:
                    os.environ.pop("BNPM_DATA_DIR", None)
                else:
                    os.environ["BNPM_DATA_DIR"] = old_data

    def test_file_uri_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp).resolve()
            uri = path_to_file_uri(path)

            self.assertTrue(uri.startswith("file://"))
            self.assertEqual(file_uri_to_path(uri), path)

    def test_plugin_dir_encodes_dot_segments(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            path = plugin_dir(
                home,
                "https://github.com/user/../../evil.git",
                "abc123",
            )

        self.assertIn("%2E%2E", path.parts)
        self.assertTrue(path.is_relative_to(home.resolve()))

    def test_plugin_dir_handles_ssh_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            path = plugin_dir(
                Path(temp),
                "git@github.com:user/repo.git",
                "abc123",
        )

        self.assertEqual(path.name, "abc123")
        self.assertIn("github%2Ecom", path.parts)

    def test_plugin_dir_encodes_path_segments(self):
        with tempfile.TemporaryDirectory() as temp:
            path = plugin_dir(
                Path(temp),
                "https://git.example.com/user/repo:name.git",
                "abc123",
            )

        self.assertIn("repo%3Aname", path.parts)

    def test_plugin_dir_handles_tilde_and_backslash_segments(self):
        with tempfile.TemporaryDirectory() as temp:
            path = plugin_dir(
                Path(temp),
                "https://git.example.com/user/repo~name\\extra.git",
                "abc123",
            )

        self.assertIn("repo%7Ename%5Cextra", path.parts)

    def test_path_install_dir_expands_user_home(self):
        path = install_dir(
            Path("unused"),
            SourceSpec(name="local", kind="path", path="~"),
            "unused",
        )

        self.assertEqual(path, Path.home().resolve())

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

                code = main(["--manifest-path", str(manifest), "--home", str(root / "home"), "sync"])
            finally:
                os.chdir(old_cwd)

            locked = load_lockfile(config / "bnpm.lock").plugins
            self.assertEqual(code, 0)
            self.assertEqual(len(locked), 1)
            self.assertEqual(locked[0].source, path_to_file_uri(plugin))

    def test_packed_binaryninja_loader_can_import_bnpm_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin_root = root / "bnpm"
            build_bundle(plugin_root)

            binaryninja = types.ModuleType("binaryninja")
            binaryninja.PluginCommand = type(
                "PluginCommand",
                (),
                {"register": staticmethod(lambda *args, **kwargs: None)},
            )
            binaryninja.log_error = lambda *args, **kwargs: None
            binaryninja.log_info = lambda *args, **kwargs: None

            saved_modules = {
                name: module
                for name, module in sys.modules.items()
                if name == "bnpm" or name.startswith("bnpm.")
            }
            for name in saved_modules:
                sys.modules.pop(name, None)

            try:
                with patch.dict(
                    os.environ,
                    {
                        "BNPM_CONFIG_DIR": str(root / "config"),
                        "BNPM_DATA_DIR": str(root / "data"),
                    },
                ), patch.dict(sys.modules, {"binaryninja": binaryninja}):
                    spec = importlib.util.spec_from_file_location(
                        "bnpm",
                        plugin_root / "__init__.py",
                        submodule_search_locations=[str(plugin_root)],
                    )
                    assert spec is not None
                    module = importlib.util.module_from_spec(spec)
                    sys.modules["bnpm"] = module
                    assert spec.loader is not None
                    spec.loader.exec_module(module)

                    import bnpm.runtime

                    self.assertEqual(
                        Path(bnpm.runtime.__file__).resolve(),
                        (plugin_root / "bnpm" / "runtime.py").resolve(),
                    )
            finally:
                for name in [name for name in sys.modules if name == "bnpm" or name.startswith("bnpm.")]:
                    sys.modules.pop(name, None)
                sys.modules.update(saved_modules)


if __name__ == "__main__":
    unittest.main()
