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


class Clips(unittest.TestCase):
    """Videos added through the interface become short silent clips among the pictures."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from radiokiosk import gallery
        self.module = gallery
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name) / "pictures"
        self.folder.mkdir()
        cache = mock.patch.object(gallery, "SCALED", Path(folder.name) / "cache")
        cache.start()
        self.addCleanup(cache.stop)
        self.gallery = gallery.Gallery({"gallery": {"folder": str(self.folder)}})

    def test_a_clip_takes_its_turn_among_the_pictures_and_a_plain_video_does_not(self):
        for name in ("a.jpg", "b.clip.mp4", "c.mp4", ".d.clip.mp4.part"):
            (self.folder / name).write_bytes(b"")
        self.assertEqual([p.name for p in self.module.find_pictures(self.folder)], ["a.jpg", "b.clip.mp4"])
        self.assertEqual(self.gallery.info()["clips"], [1])
        self.assertEqual([p["clip"] for p in self.gallery.listing()], [False, True])
        self.assertIsNone(self.gallery.clip(0))
        self.assertEqual(self.gallery.clip(1), self.folder / "b.clip.mp4")

    def test_many_kinds_of_video_are_taken_and_pictures_stay_pictures(self):
        for name in ("a.MOV", "b.mkv", "c.avi", "d.3gp", "e.MTS", "f.webm", "g.wmv", "h.mpg"):
            self.assertTrue(self.module.is_video(name), name)
        for name in ("a.jpg", "b.gif", "c.txt", "noending"):
            self.assertFalse(self.module.is_video(name), name)

    def test_the_clip_is_cut_silent_and_small(self):
        command = self.module.clip_command("in.mov", "out.mp4")
        self.assertEqual(command[command.index("-t") + 1], "30")
        self.assertIn("-an", command)
        self.assertIn("fps=20", command[command.index("-vf") + 1])

    @unittest.skipUnless(__import__("shutil").which("ffmpeg") and __import__("shutil").which("ffprobe"), "needs ffmpeg")
    def test_a_video_becomes_a_clip_and_what_is_no_video_leaves_nothing_behind(self):
        import subprocess
        source = self.folder.parent / "long holiday.mkv"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=33",
                        "-f", "lavfi", "-i", "sine=duration=33", "-c:v", "mpeg4", "-q:v", "20", "-c:a", "mp2", str(source)], check=True)
        self.gallery.add_video(source.name, source)
        self.gallery.add_video(source.name, source)   # the same name again never replaces the first
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["long holiday-2.clip.mp4", "long holiday.clip.mp4"])
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "default=nw=1",
             str(self.folder / "long holiday.clip.mp4")], capture_output=True, text=True).stdout
        self.assertNotIn("audio", probe)
        self.assertIn("width=960", probe)
        self.assertIn("height=540", probe)
        self.assertIn("duration=30.0", probe)
        # as a picture a clip is its first one: thumbnail and backdrop
        self.gallery.refresh(True)
        with self.module.Image.open(self.gallery.picture(0, 240, 240)) as picture:
            self.assertEqual(picture.size, (320, 180))
        broken = self.folder.parent / "broken.mp4"
        broken.write_text("no video")
        with self.assertRaises(ValueError):
            self.gallery.add_video(broken.name, broken)
        self.assertEqual(len(list(self.folder.iterdir())), 2)
