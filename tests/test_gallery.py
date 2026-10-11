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
        for key, value in (("folder", "/no/such/folder"), ("seconds", 7), ("shuffle", "yes"), ("fit", "stretch"),
                           ("effect", "explode"), ("pan", "left"), ("pan_range", 10)):
            with self.assertRaises(ValueError):
                gallery.check(key, value)

    def test_effects_between_pictures_can_be_chosen(self):
        from radiokiosk.gallery import EFFECTS
        gallery = Gallery({})
        self.assertEqual(gallery.settings["effect"], "fade")
        self.assertEqual([gallery.check("effect", effect) for effect in EFFECTS], list(EFFECTS))

    def test_a_missing_folder_means_no_pictures_not_an_error(self):
        gallery = Gallery({"gallery": {"folder": "/no/such/folder"}})
        self.assertEqual((gallery.info()["count"], gallery.info()["missing"]), (0, True))
        self.assertIsNone(gallery.picture(0, 800, 480))


class ManagingPictures(unittest.TestCase):
    """Pictures added and deleted through the interface."""

    def setUp(self):
        import io
        import tempfile
        from pathlib import Path
        from radiokiosk import gallery
        self.gallery_module = gallery
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.gallery = gallery.Gallery({"gallery": {"folder": str(self.folder)}})
        picture = io.BytesIO()
        gallery.Image.new("RGB", (8, 6), "red").save(picture, "JPEG")
        self.jpeg = picture.getvalue()

    def test_the_backdrop_is_a_small_dark_copy_made_once(self):
        from unittest import mock
        cache = self.folder / "cache"
        with mock.patch.object(self.gallery_module, "SCALED", cache):
            self.gallery_module.Image.new("RGB", (300, 900), "white").save(self.folder / "tall.jpg", "JPEG")
            self.gallery.refresh(True)
            first = self.gallery.picture(0, 800, 480, back=True)
            with self.gallery_module.Image.open(first) as picture:
                self.assertLessEqual(max(picture.size), 320)
                self.assertLess(picture.getpixel((50, 150))[0], 180)      # white, darkened
            self.assertNotEqual(first, self.gallery.picture(0, 800, 480))
            made = first.stat().st_mtime_ns
            self.assertEqual(self.gallery.picture(0, 800, 480, back=True).stat().st_mtime_ns, made)

    def test_added_pictures_never_replace_each_other(self):
        self.gallery.add("holiday.jpg", self.jpeg)
        self.gallery.add("../../holiday.jpg", self.jpeg)          # a path from outside counts as a name only
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["holiday-2.jpg", "holiday.jpg"])
        self.assertEqual([p["name"] for p in self.gallery.listing()], ["holiday-2.jpg", "holiday.jpg"])

    def test_what_is_no_picture_is_refused(self):
        for name, data in (("notes.txt", self.jpeg), ("fake.jpg", b"not a picture at all"), ("", self.jpeg)):
            with self.assertRaises(ValueError):
                self.gallery.add(name, data)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_only_pictures_of_the_folder_can_be_deleted(self):
        self.gallery.add("a.jpg", self.jpeg)
        outside = self.folder.parent / "outside-of-gallery.jpg"
        outside.write_bytes(self.jpeg)
        self.addCleanup(outside.unlink)
        (self.folder / "list.txt").write_text("keep")
        for name in ("../outside-of-gallery.jpg", str(outside), "list.txt", "missing.jpg"):
            with self.assertRaises(ValueError):
                self.gallery.remove(name)
        self.gallery.remove("a.jpg")
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["list.txt"])

    def test_the_demo_pictures_cannot_be_deleted(self):
        demo = self.gallery_module.Gallery({"gallery": {}})
        with self.assertRaises(ValueError):
            demo.remove(demo.listing()[0]["name"])
