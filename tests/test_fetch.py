from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bnpm.fetch import install
from bnpm.installed import read_installed_plugin
from bnpm.source import SourceSpec


class FetchTests(unittest.TestCase):
    def test_git_install_writes_metadata_at_stable_plugin_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"

            def fake_run_git(args, cwd):
                if args[:3] == ["git", "clone", "--quiet"]:
                    checkout = Path(args[-1])
                    checkout.mkdir()
                    checkout.joinpath("__init__.py").write_text(
                        "VALUE = 1\n", encoding="utf-8"
                    )
                    return ""
                if args[:3] == ["git", "rev-parse", "HEAD"]:
                    return "abc123"
                return ""

            with patch("bnpm.fetch._run_git", side_effect=fake_run_git):
                locked = install(
                    SourceSpec(
                        name="stable",
                        kind="git",
                        git="https://github.com/user/stable.git",
                    ),
                    home,
                )

            target = home / "stable"
            installed = read_installed_plugin(target)
            self.assertEqual(locked.commit, "abc123")
            self.assertTrue(target.joinpath("__init__.py").exists())
            self.assertFalse((target / "abc123").exists())
            self.assertIsNotNone(installed)
            assert installed is not None
            self.assertEqual(installed.name, locked.name)
            self.assertEqual(installed.source, locked.source)
            self.assertEqual(installed.commit, locked.commit)
            self.assertEqual(installed.checksum, locked.checksum)
            self.assertEqual(list(home.glob(".*.tmp")), [])

    def test_git_install_rolls_back_existing_target_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            target = home / "stable"
            target.mkdir(parents=True)
            target.joinpath("__init__.py").write_text(
                "VALUE = 'old'\n", encoding="utf-8"
            )

            def fake_run_git(args, cwd):
                if args[:3] == ["git", "clone", "--quiet"]:
                    checkout = Path(args[-1])
                    checkout.mkdir()
                    checkout.joinpath("__init__.py").write_text(
                        "VALUE = 'new'\n", encoding="utf-8"
                    )
                    return ""
                if args[:3] == ["git", "rev-parse", "HEAD"]:
                    return "abc123"
                return ""

            with (
                patch("bnpm.fetch._run_git", side_effect=fake_run_git),
                patch(
                    "bnpm.fetch.Path.rename",
                    side_effect=OSError("replace failed"),
                ),
            ):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    install(
                        SourceSpec(
                            name="stable",
                            kind="git",
                            git="https://github.com/user/stable.git",
                        ),
                        home,
                    )

            self.assertEqual(
                target.joinpath("__init__.py").read_text(encoding="utf-8"),
                "VALUE = 'old'\n",
            )
            self.assertEqual(list(home.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
