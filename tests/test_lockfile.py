from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from bnpm.lockfile import LockedPackage, LockedPlugin, load_lockfile, write_lockfile
from bnpm.status import load_manifest_plugins, collect_lock_mismatches


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

    def test_load_lockfile_rejects_invalid_dependency_type(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bnpm.lock"
            path.write_text(
                """
version = 1

[[plugins]]
name = "hexpatch"
source = "https://github.com/user/hexpatch.git"
checksum = "sha256:deadbeef"
dependencies = "requests"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError, "plugins.dependencies must be a list of strings"
            ):
                load_lockfile(path)

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

            collect_manifest_plugins = load_manifest_plugins(manifest)
            mismatches = collect_lock_mismatches(
                collect_manifest_plugins, load_lockfile(lock)
            )

        self.assertEqual(
            mismatches, ["plugin 'local' is in bnpm.toml but not bnpm.lock"]
        )

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

            collect_manifest_plugins = load_manifest_plugins(manifest)
            mismatches = collect_lock_mismatches(
                collect_manifest_plugins, load_lockfile(lock)
            )

        self.assertEqual(mismatches, ["plugin 'local' source changed"])
