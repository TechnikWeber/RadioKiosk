"""Choosing a release and turning the link; fetching and switching need a device and are tried there."""

import os
import tempfile
import unittest
from pathlib import Path

from radiokiosk.update import newest, numbers, repo_of, turn


class ReleaseChoice(unittest.TestCase):
    def test_versions_compare_as_numbers(self):
        self.assertEqual(numbers("v0.19.0"), (0, 19, 0))
        self.assertGreater(numbers("v0.100.0"), numbers("v0.20.3"))
        self.assertIsNone(numbers("nightly"))
        self.assertIsNone(numbers(None))

    def test_newest_skips_drafts_and_other_tags(self):
        releases = [{"tag_name": "v0.9.0"}, {"tag_name": "v0.20.0", "draft": True}, {"tag_name": "v0.19.0", "prerelease": True},
                    {"tag_name": "test-build"}, "nonsense"]
        self.assertEqual(newest(releases)["tag_name"], "v0.19.0")
        self.assertIsNone(newest([]))

    def test_repo_from_the_addresses_git_stores(self):
        self.assertEqual(repo_of("https://github.com/TechnikWeber/RadioKiosk.git\n"), "TechnikWeber/RadioKiosk")
        self.assertEqual(repo_of("git@github.com:TechnikWeber/RadioKiosk"), "TechnikWeber/RadioKiosk")
        self.assertIsNone(repo_of("https://example.org/some/repo.git"))


class Link(unittest.TestCase):
    def test_turning_replaces_the_link_and_leaves_nothing_behind(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "old").mkdir()
            (folder / "new").mkdir()
            link = folder / "current"
            turn(link, folder / "old")
            turn(link, folder / "new")
            self.assertEqual(link.resolve(), (folder / "new").resolve())
            self.assertEqual(sorted(os.listdir(folder)), ["current", "new", "old"])
