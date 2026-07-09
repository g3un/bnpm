from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from bnpm.installed import read_installed_plugin, write_installed_plugin
from bnpm.config import get_config
from bnpm.utils.hash import compute_tree_sha256
from bnpm.lockfile import LockedPlugin
from bnpm.source import SourceSpec
from bnpm.utils.locations import (
    convert_file_uri_to_path,
    resolve_install_dir,
    resolve_package_dir,
    resolve_plugin_dir,
    convert_path_to_file_uri,
)
from tests.helpers import clear_bnpm_caches


class UtilsTests(unittest.TestCase):
    def setUp(self):
        clear_bnpm_caches()

    def test_default_paths_use_platform_config_and_data_dirs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            appdata = root / "roaming"
            localappdata = root / "local"
            with (
                patch("bnpm.config.platform.system", return_value="Windows"),
                patch.dict(
                    os.environ,
                    {
                        "APPDATA": str(appdata),
                        "LOCALAPPDATA": str(localappdata),
                    },
                ),
            ):
                config = get_config()
                self.assertEqual(config.bnpm_config_dir, appdata / "bnpm")
                self.assertEqual(
                    config.bnpm_manifest_path, appdata / "bnpm" / "bnpm.toml"
                )
                self.assertEqual(
                    config.bnpm_plugin_dir, localappdata / "bnpm" / "plugins"
                )
                self.assertEqual(
                    resolve_package_dir(config.bnpm_plugin_dir),
                    localappdata / "bnpm" / "packages",
                )
                self.assertEqual(config.bnpm_venv_dir, localappdata / "bnpm" / "venv")

    def test_file_uri_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp).resolve()
            uri = convert_path_to_file_uri(path)

            self.assertTrue(uri.startswith("file://"))
            self.assertEqual(convert_file_uri_to_path(uri), path)

    def test_file_uri_rejects_non_file_uri(self):
        with self.assertRaisesRegex(ValueError, "not a file URI"):
            convert_file_uri_to_path("https://example.com/plugin")

    def test_plugin_dir_rejects_empty_name(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "empty plugin path segment"):
                resolve_plugin_dir(Path(temp), "")

    def test_plugin_dir_encodes_plugin_name(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            path = resolve_plugin_dir(home, "user/../../evil")

        self.assertIn("user%2F..%2F..%2Fevil", path.parts)
        self.assertTrue(path.is_relative_to(home.resolve()))

    def test_plugin_dir_uses_plugin_name(self):
        with tempfile.TemporaryDirectory() as temp:
            path = resolve_plugin_dir(Path(temp), "registered-name")

        self.assertEqual(path.name, "registered-name")

    def test_plugin_dir_encodes_colons(self):
        with tempfile.TemporaryDirectory() as temp:
            path = resolve_plugin_dir(Path(temp), "repo:name")

        self.assertIn("repo%3Aname", path.parts)

    def test_plugin_dir_encodes_backslash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = resolve_plugin_dir(Path(temp), "repo~name\\extra")

        self.assertIn("repo~name%5Cextra", path.parts)

    def test_path_install_dir_expands_user_home(self):
        path = resolve_install_dir(
            Path("unused"),
            SourceSpec(name="local", kind="path", path="~"),
        )

        self.assertEqual(path, Path.home().resolve())

    def test_installed_metadata_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            locked = LockedPlugin(
                name="hexpatch",
                source="https://github.com/user/hexpatch.git",
                version="tag:v1.2.3",
                checksum="sha256:deadbeef",
                commit="abc123",
            )

            write_installed_plugin(root, locked)
            installed = read_installed_plugin(root)

        self.assertIsNotNone(installed)
        assert installed is not None
        self.assertEqual(installed.name, "hexpatch")
        self.assertEqual(installed.version, "tag:v1.2.3")
        self.assertEqual(installed.commit, "abc123")
        self.assertEqual(installed.checksum, "sha256:deadbeef")

    def test_tree_sha256_ignores_installed_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.joinpath("__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            before = compute_tree_sha256(root)

            write_installed_plugin(
                root,
                LockedPlugin(
                    name="hexpatch",
                    source="https://github.com/user/hexpatch.git",
                    version="HEAD",
                    checksum="sha256:metadata",
                    commit="abc123",
                ),
            )

            self.assertEqual(compute_tree_sha256(root), before)

    def test_tree_sha256_hashes_symlink_target_not_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "root"
            root.mkdir()
            outside = base / "outside.txt"
            outside.write_text("one", encoding="utf-8")
            file_link = root / "file-link"
            file_link.symlink_to(outside)
            dir_link = root / "dir-link"
            dir_link.symlink_to(base)
            before = compute_tree_sha256(root)

            outside.write_text("two", encoding="utf-8")

            self.assertEqual(compute_tree_sha256(root), before)
