import tempfile
import unittest
from pathlib import Path

from radiokiosk.gallery import Gallery, box_for, find_pictures, subfolders


class GalleryTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        for name in ("b.jpg", "a.PNG", "notes.txt", ".hidden.jpg", "trip/c.jpeg", ".cache/d.jpg"):
            (self.folder / name).parent.mkdir(exist_ok=True)
            (self.folder / name).write_bytes(b"")

    def test_finds_pictures_in_subfolders_but_nothing_hidden(self):
        names = [str(p.relative_to(self.folder)) for p in find_pictures(self.folder)]
        self.assertEqual(names, ["a.PNG", "b.jpg", "trip/c.jpeg"])

    def test_without_subfolders_only_the_folder_itself_counts(self):
        self.assertEqual([p.name for p in find_pictures(self.folder, deep=False)], ["a.PNG", "b.jpg"])

    def test_folder_picker_counts_only_what_lies_directly_in_the_folder(self):
        listing = subfolders(self.folder)
        self.assertEqual((listing["folders"], listing["pictures"]), (["trip"], 2))

    def test_the_scaling_step_is_the_smallest_that_fills_the_screen(self):
        self.assertEqual([box_for(800, 480), box_for(1920, 1080), box_for(3840, 2160)], [960, 2560, 2560])

    def test_settings_from_the_interface_are_validated(self):
        gallery = Gallery({})
        self.assertEqual(gallery.check("folder", str(self.folder)), str(self.folder))
        for key, value in (("folder", "/no/such/folder"), ("seconds", 7), ("shuffle", "yes"), ("fit", "stretch")):
            with self.assertRaises(ValueError):
                gallery.check(key, value)

    def test_a_missing_folder_means_no_pictures_not_an_error(self):
        gallery = Gallery({"gallery": {"folder": "/no/such/folder"}})
        self.assertEqual((gallery.info()["count"], gallery.info()["missing"]), (0, True))
        self.assertIsNone(gallery.picture(0, 800, 480))
