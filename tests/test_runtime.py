from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
from pathlib import Path
import unittest
from unittest.mock import patch

from bnpm.setup import install_plugin_files
from bnpm.installed import write_installed_plugin
from bnpm.utils.hash import compute_tree_sha256
from bnpm.lockfile import LockedPlugin, load_lockfile, write_lockfile
from bnpm.runtime import activate, build_plugin_python_env
from bnpm.sync import sync
from bnpm.utils.locations import (
    resolve_package_dir,
    resolve_plugin_dir,
    convert_path_to_file_uri,
)
from bnpm.config import get_config
from tests.helpers import clear_bnpm_caches


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        clear_bnpm_caches()

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

            sync(
                manifest_path=manifest, lock_path=root / "bnpm.lock", home=root / "home"
            )
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

            sync(
                manifest_path=manifest, lock_path=root / "bnpm.lock", home=root / "home"
            )

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

            sync(
                manifest_path=manifest, lock_path=root / "bnpm.lock", home=root / "home"
            )

            activate(lock_path=root / "bnpm.lock", home=root / "home")

            self.assertEqual(marker.read_text(encoding="utf-8"), "ok")

    def test_runtime_package_dir_processes_pth_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            packages = resolve_package_dir(home)
            packages.mkdir(parents=True)
            extra = packages / "extra"
            extra.mkdir()
            extra.joinpath("pth_dependency.py").write_text(
                "VALUE = 'ok'\n", encoding="utf-8"
            )
            packages.joinpath("dependency.pth").write_text("extra\n", encoding="utf-8")
            plugin = root / "plugin"
            plugin.mkdir()
            marker = root / "loaded.txt"
            plugin.joinpath("__init__.py").write_text(
                f"from pathlib import Path\nimport pth_dependency\nPath({str(marker)!r}).write_text(pth_dependency.VALUE, encoding='utf-8')\n",
                encoding="utf-8",
            )
            lock = root / "bnpm.lock"
            write_lockfile(
                lock,
                [
                    LockedPlugin(
                        name="pth-local",
                        source=convert_path_to_file_uri(plugin),
                        checksum=compute_tree_sha256(plugin),
                    )
                ],
            )

            activate(lock_path=lock, home=home)

            self.assertEqual(marker.read_text(encoding="utf-8"), "ok")

    def test_plugin_python_env_adds_plugin_and_dependency_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            plugin = root / "plugin"
            package = plugin / "src" / "sample_plugin"
            package.mkdir(parents=True)
            plugin.joinpath("pyproject.toml").write_text(
                """
[project]
name = "sample-plugin"
dependencies = []
""".strip(),
                encoding="utf-8",
            )
            package.joinpath("__init__.py").write_text("", encoding="utf-8")
            resolve_package_dir(home).mkdir(parents=True)
            lock = root / "bnpm.lock"
            write_lockfile(
                lock,
                [
                    LockedPlugin(
                        name="local",
                        source=convert_path_to_file_uri(plugin),
                        version="local",
                        checksum=compute_tree_sha256(plugin),
                    )
                ],
            )

            env = build_plugin_python_env(
                "local",
                lock_path=lock,
                home=home,
                env={"PYTHONPATH": "existing"},
            )

            pythonpath = env["PYTHONPATH"].split(os.pathsep)
            self.assertEqual(Path(pythonpath[0]).resolve(), (plugin / "src").resolve())
            self.assertEqual(
                Path(pythonpath[1]).resolve(), resolve_package_dir(home).resolve()
            )
            self.assertEqual(pythonpath[-1], "existing")
            self.assertEqual(env["VIRTUAL_ENV"], str(get_config().bnpm_venv_dir))

    def test_plugin_python_env_reports_missing_locked_plugin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = root / "bnpm.lock"
            write_lockfile(lock, [])

            with self.assertRaisesRegex(
                Exception, "missing: plugin is not in bnpm.lock"
            ):
                build_plugin_python_env(
                    "missing", lock_path=lock, home=root / "home", env={}
                )

    def test_plugin_python_env_reports_missing_entry_point(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            plugin = root / "plugin"
            plugin.mkdir()
            lock = root / "bnpm.lock"
            write_lockfile(
                lock,
                [
                    LockedPlugin(
                        name="local",
                        source=convert_path_to_file_uri(plugin),
                        checksum=compute_tree_sha256(plugin),
                    )
                ],
            )

            with self.assertRaisesRegex(Exception, "local: missing plugin entry point"):
                build_plugin_python_env("local", lock_path=lock, home=home, env={})

    def test_git_plugin_checksum_mismatch_skips_runtime_load(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            commit = "abc123"
            plugin = resolve_plugin_dir(home, "bad")
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
                        source="https://github.com/user/plugin.git",
                        version="HEAD",
                        checksum="sha256:not-the-real-hash",
                        commit=commit,
                    )
                ],
            )

            activate(lock_path=lock, home=home)

            self.assertFalse(marker.exists())

    def test_git_plugin_loads_when_install_metadata_matches_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            plugin = resolve_plugin_dir(home, "good")
            plugin.mkdir(parents=True)
            marker = root / "loaded.txt"
            plugin.joinpath("__init__.py").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('ok', encoding='utf-8')\n",
                encoding="utf-8",
            )
            locked = LockedPlugin(
                name="good",
                source="https://github.com/user/plugin.git",
                version="HEAD",
                checksum="sha256:metadata",
                commit="abc123",
            )
            write_installed_plugin(plugin, locked)
            lock = root / "bnpm.lock"
            write_lockfile(lock, [locked])

            activate(lock_path=lock, home=home)

            self.assertEqual(marker.read_text(encoding="utf-8"), "ok")

    def test_git_plugin_skips_when_install_metadata_differs_from_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            plugin = resolve_plugin_dir(home, "stale")
            plugin.mkdir(parents=True)
            marker = root / "loaded.txt"
            plugin.joinpath("__init__.py").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('stale', encoding='utf-8')\n",
                encoding="utf-8",
            )
            installed = LockedPlugin(
                name="stale",
                source="https://github.com/user/plugin.git",
                version="HEAD",
                checksum="sha256:old",
                commit="abc123",
            )
            locked = LockedPlugin(
                name="stale",
                source="https://github.com/user/plugin.git",
                version="HEAD",
                checksum="sha256:new",
                commit="abc123",
            )
            write_installed_plugin(plugin, installed)
            lock = root / "bnpm.lock"
            write_lockfile(lock, [locked])

            activate(lock_path=lock, home=home)

            self.assertFalse(marker.exists())

    def test_git_plugin_loads_tampered_install_when_metadata_matches_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            plugin = resolve_plugin_dir(home, "tampered")
            plugin.mkdir(parents=True)
            marker = root / "loaded.txt"
            init_path = plugin / "__init__.py"
            init_path.write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('ok', encoding='utf-8')\n",
                encoding="utf-8",
            )
            locked = LockedPlugin(
                name="tampered",
                source="https://github.com/user/plugin.git",
                version="HEAD",
                checksum=compute_tree_sha256(plugin),
                commit="abc123",
            )
            write_installed_plugin(plugin, locked)
            init_path.write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad', encoding='utf-8')\n",
                encoding="utf-8",
            )
            lock = root / "bnpm.lock"
            write_lockfile(lock, [locked])

            activate(lock_path=lock, home=home)

            self.assertEqual(marker.read_text(encoding="utf-8"), "bad")

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

    def test_packed_binaryninja_loader_can_import_bnpm_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin_root = root / "bnpm"
            install_plugin_files(plugin_root)
            registered_commands = []

            binaryninja = types.ModuleType("binaryninja")
            binaryninja.PluginCommand = type(
                "PluginCommand",
                (),
                {
                    "register": staticmethod(
                        lambda *args, **kwargs: registered_commands.append(
                            (args, kwargs)
                        )
                    )
                },
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
                with patch.dict(sys.modules, {"binaryninja": binaryninja}):
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

                    self.assertFalse((plugin_root / "bnpm" / "cli").exists())
                    self.assertEqual(
                        Path(bnpm.runtime.__file__).resolve(),
                        (plugin_root / "bnpm" / "runtime" / "__init__.py").resolve(),
                    )
                    self.assertEqual(registered_commands[0][0][0], "BNPM\\Sync")
                    with self.assertRaises(ModuleNotFoundError):
                        __import__("bnpm.cli")
            finally:
                for name in [
                    name
                    for name in sys.modules
                    if name == "bnpm" or name.startswith("bnpm.")
                ]:
                    sys.modules.pop(name, None)
                sys.modules.update(saved_modules)


if __name__ == "__main__":
    unittest.main()
