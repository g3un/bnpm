from __future__ import annotations

import unittest

from bnpm.source import parse_plugin


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

    def test_github_table_does_not_double_git_suffix(self):
        spec = parse_plugin("hexpatch", {"git": "github.com/user/hexpatch.git"})

        self.assertEqual(spec.git, "https://github.com/user/hexpatch.git")

    def test_git_table_with_latest_version_tag(self):
        spec = parse_plugin(
            "hexpatch",
            {
                "git": "https://github.com/user/hexpatch.git",
                "latest-version-tag": True,
            },
        )

        self.assertTrue(spec.latest_tag)
        self.assertEqual(spec.version, "latest-version-tag")

    def test_table_cannot_set_multiple_refs(self):
        with self.assertRaisesRegex(Exception, "can only set one of tag, branch, rev"):
            parse_plugin(
                "hexpatch",
                {
                    "git": "https://github.com/user/hexpatch.git",
                    "tag": "v1.0.0",
                    "branch": "main",
                },
            )

    def test_table_cannot_set_git_and_path(self):
        with self.assertRaisesRegex(Exception, "cannot set both git and path"):
            parse_plugin(
                "hexpatch",
                {"git": "https://github.com/user/hexpatch.git", "path": "plugin"},
            )

    def test_git_without_ref_uses_head_version(self):
        spec = parse_plugin("hexpatch", "github.com/user/hexpatch")

        self.assertEqual(spec.version, "HEAD")

    def test_query_string_refs_are_not_supported(self):
        with self.assertRaisesRegex(Exception, "query strings are not supported"):
            parse_plugin("hexpatch", "github.com/user/hexpatch?branch=main")

    def test_inline_refs_are_not_supported(self):
        with self.assertRaisesRegex(Exception, "inline refs are not supported"):
            parse_plugin("hexpatch", "github.com/user/hexpatch@v1.2.3")

    def test_http_git_url_is_rejected(self):
        with self.assertRaisesRegex(Exception, "insecure git URL"):
            parse_plugin("hexpatch", "http://github.com/user/hexpatch.git")

    def test_ssh_shorthand_does_not_treat_at_as_tag(self):
        spec = parse_plugin("hexpatch", "git@github.com:user/hexpatch.git")

        self.assertEqual(spec.git, "git@github.com:user/hexpatch.git")
        self.assertEqual(spec.version, "HEAD")
