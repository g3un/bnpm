from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from bnpm.manifest import load_manifest
from bnpm.utils.toml import _parse_subset

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

    def test_load_manifest_rejects_unsupported_version(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bnpm.toml"
            path.write_text("version = 2\n", encoding="utf-8")

            with self.assertRaisesRegex(Exception, "unsupported bnpm.toml version"):
                load_manifest(path)

    def test_load_manifest_rejects_non_table_plugins(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bnpm.toml"
            path.write_text('version = 1\nplugins = "bad"\n', encoding="utf-8")

            with self.assertRaisesRegex(Exception, r"\[plugins\] must be a table"):
                load_manifest(path)

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


