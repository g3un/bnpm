from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest

from bnpm.cli import main
from bnpm.lockfile import LockedPlugin, load_lockfile, write_lockfile
from bnpm.manifest import load_manifest
from bnpm.runtime import activate
from bnpm.source import SourceSpec, parse_plugin
from bnpm.status import load_manifest_plugins, lock_mismatches
from bnpm.store import (
    default_config_dir,
    default_home,
    default_manifest_path,
    file_uri_to_path,
    install_dir,
    managed_git_dir,
    path_to_file_uri,
)
from bnpm.toml_compat import _parse_subset


class SourceTests(unittest.TestCase):
    def test_github_shorthand_with_tag(self):
        spec = parse_plugin("hexpatch", "github.com/user/hexpatch@v1.2.3")

        self.assertEqual(spec.name, "hexpatch")
        self.assertEqual(spec.kind, "git")
        self.assertEqual(spec.git, "https://github.com/user/hexpatch.git")
        self.assertEqual(spec.tag, "v1.2.3")

    def test_git_table_with_rev(self):
        spec = parse_plugin(
            "hexpatch",
            {"git": "https://github.com/user/hexpatch.git", "rev": "abc123"},
        )

        self.assertEqual(spec.version, "rev:abc123")

    def test_git_without_ref_uses_head_version(self):
        spec = parse_plugin("hexpatch", "github.com/user/hexpatch")

        self.assertEqual(spec.version, "HEAD")


class ManifestTests(unittest.TestCase):
    def test_load_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bnpm.toml"
            path.write_text(
                """
version = 1

[plugins]
hexpatch = "github.com/user/hexpatch@v1.2.3"
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
hexpatch = "github.com/user/hexpatch@v1.2.3"
devtools = { git = "https://github.com/user/devtools.git", branch = "main" }
""".strip()
        )

        self.assertEqual(data["version"], 1)
        self.assertEqual(data["plugins"]["devtools"]["branch"], "main")


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
                    )
                ],
            )
            lockfile = load_lockfile(path)

        self.assertEqual(lockfile.plugins[0].name, "hexpatch")
        self.assertEqual(lockfile.plugins[0].version, "tag:v1.2.3")
        self.assertEqual(lockfile.plugins[0].commit, "abc123")

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

            code = main(
                [
                    "--manifest-path",
                    str(manifest),
                    "--home",
                    str(root / "home"),
                    "add",
                    "local",
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

    def test_add_existing_source_path_treats_it_as_path_plugin(self):
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
                    str(plugin),
                ]
            )

            self.assertEqual(code, 0)
            self.assertEqual(load_manifest(manifest).plugins["local"].kind, "path")
            self.assertEqual(load_lockfile(root / "bnpm.lock").plugins[0].source, plugin.resolve().as_uri())

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
local = { path = "plugin" }
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

    def test_git_plugin_checksum_mismatch_skips_runtime_load(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            source = "https://github.com/user/plugin.git"
            commit = "abc123"
            plugin = managed_git_dir(home, source, commit)
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
            root = Path(temp)
            old_config = os.environ.get("BNPM_CONFIG_DIR")
            old_data = os.environ.get("BNPM_DATA_DIR")
            try:
                os.environ["BNPM_CONFIG_DIR"] = str(root / "config")
                os.environ["BNPM_DATA_DIR"] = str(root / "data")

                self.assertEqual(default_config_dir(), root / "config")
                self.assertEqual(default_manifest_path(), root / "config" / "bnpm.toml")
                self.assertEqual(default_home(), root / "data" / "plugins")
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

    def test_managed_git_dir_encodes_dot_segments(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            path = managed_git_dir(
                home,
                "https://github.com/user/../../evil.git",
                "abc123",
            )

        self.assertIn("%2E%2E", path.parts)
        self.assertTrue(path.is_relative_to(home.resolve()))

    def test_managed_git_dir_handles_ssh_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            path = managed_git_dir(
                Path(temp),
                "git@github.com:user/repo.git",
                "abc123",
        )

        self.assertEqual(path.name, "abc123")
        self.assertIn("github%2Ecom", path.parts)

    def test_managed_git_dir_encodes_path_segments(self):
        with tempfile.TemporaryDirectory() as temp:
            path = managed_git_dir(
                Path(temp),
                "https://git.example.com/user/repo:name.git",
                "abc123",
            )

        self.assertIn("repo%3Aname", path.parts)

    def test_managed_git_dir_handles_tilde_and_backslash_segments(self):
        with tempfile.TemporaryDirectory() as temp:
            path = managed_git_dir(
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


if __name__ == "__main__":
    unittest.main()
