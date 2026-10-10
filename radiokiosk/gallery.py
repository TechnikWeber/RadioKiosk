"""Pictures from a folder, as a slide show for the gallery tile and the idle screen.

The folder may be anything the computer can read: a local folder, a USB stick,
or a network share the user has mounted. Photos are scaled down to screen size
once and kept in the cache, so a small computer does not decode twelve megapixels
for every slide.

Nothing here knows about radio; the module stands on its own.
"""

import hashlib
import os
import time
from pathlib import Path

from .config import CACHE_DIR, WEB_DIR

try:
    from PIL import Image, ImageOps
except ImportError:   # without Pillow the pictures go out as they are
    Image = None

KINDS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
# fit: "whole" shows all of a picture, "fill" crops it to the screen, "smart" crops only where little is lost
DEFAULTS = {"folder": None, "seconds": 15, "shuffle": True, "fit": "whole", "subfolders": True}
FITS = ("whole", "smart", "fill")
DEMO = WEB_DIR.parent / "demo-pictures"   # shown until a folder is chosen
SECONDS = (5, 10, 15, 30, 60, 300)
LIMIT = 5000              # pictures taken from one folder
RESCAN_AFTER = 120        # seconds a list of pictures is trusted
SIZES = (960, 1600, 2560)  # longest edge a picture is scaled to; the smallest that fills the screen is used
SCALED = CACHE_DIR / "gallery"


def is_picture(path):
    return path.suffix.lower() in KINDS and not path.name.startswith(".")


def find_pictures(folder, deep=True):
    """The pictures in a folder, with `deep` also those below it, sorted by path. Hidden folders are left out."""
    found = []
    for root, folders, files in os.walk(folder, followlinks=True):
        folders[:] = sorted(f for f in folders if not f.startswith(".")) if deep else []
        found += [Path(root) / name for name in sorted(files) if is_picture(Path(name))]
        if len(found) >= LIMIT:
            break
    return found[:LIMIT]


def box_for(width, height):
    """The scaling step for a screen: the smallest that is at least as large."""
    wanted = max(width, height)
    return next((size for size in SIZES if size >= wanted), SIZES[-1])


def scaled(path, box):
    """The picture fitted into box x box pixels, upright, as a cached JPEG. None if it cannot be read."""
    try:
        stat = path.stat()
    except OSError:   # deleted, or the stick or share is gone
        return None
    if Image is None:
        return path
    key = hashlib.sha1(f"{path}:{stat.st_mtime_ns}:{stat.st_size}:{box}".encode()).hexdigest()
    target = SCALED / f"{key}.jpg"
    if target.exists():
        return target
    try:
        with Image.open(path) as picture:
            picture.draft("RGB", (box, box))            # lets the JPEG decoder skip most of a large photo
            picture = ImageOps.exif_transpose(picture)  # phones store portrait photos lying on their side
            picture.thumbnail((box, box))
            SCALED.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix(".part")
            picture.convert("RGB").save(partial, "JPEG", quality=85)
            partial.replace(target)
    except (OSError, ValueError, SyntaxError):
        return None
    return target


def subfolders(path):
    """What a folder picker shows for `path`: the folders in it and how many pictures lie directly in it."""
    path = Path(path).expanduser()
    try:
        entries = sorted(path.iterdir(), key=lambda e: e.name.lower())
    except OSError:
        raise RuntimeError("this folder cannot be opened")
    folders = [e.name for e in entries if not e.name.startswith(".") and e.is_dir()]
    return {"path": str(path), "parent": None if path == path.parent else str(path.parent), "folders": folders,
            "pictures": sum(1 for e in entries if is_picture(e) and e.is_file())}


def places():
    """Where a folder picker starts: the home folder and where sticks and shares usually appear."""
    user = os.environ.get("USER", "")
    candidates = [Path.home(), Path("/media") / user, Path("/run/media") / user, Path("/media"), Path("/mnt")]
    return [str(p) for p in candidates if p.is_dir()]


class Gallery:
    def __init__(self, cfg):
        self.cfg = cfg
        self.pictures = []
        self.scanned = None   # (folder, time) of the last look into the folder

    @property
    def settings(self):
        return {**DEFAULTS, **(self.cfg.get("gallery") or {})}

    def refresh(self, force=False):
        settings = self.settings
        folder = settings["folder"] or str(DEMO)
        if not force and self.scanned and self.scanned[0] == folder and time.time() - self.scanned[1] < RESCAN_AFTER:
            return
        self.pictures = find_pictures(folder, settings["subfolders"]) if Path(folder).is_dir() else []
        self.scanned = (folder, time.time())

    def info(self):
        self.refresh()
        folder = self.settings["folder"]
        return {**self.settings, "count": len(self.pictures), "missing": bool(folder) and not Path(folder).is_dir(),
                "demo": not folder, "start": folder or str(Path.home()), "places": places()}

    def check(self, key, value):
        """A setting from the interface, validated; raises ValueError for anything else."""
        if key == "folder" and isinstance(value, str) and Path(value).expanduser().is_dir():
            return str(Path(value).expanduser())
        if key == "seconds" and value in SECONDS:
            return value
        if key in ("shuffle", "subfolders") and isinstance(value, bool):
            return value
        if key == "fit" and value in FITS:
            return value
        raise ValueError("unknown setting")

    def picture(self, index, width, height):
        """File to send for picture number `index`; the numbers wrap around."""
        self.refresh()
        if not self.pictures:
            return None
        return scaled(self.pictures[index % len(self.pictures)], box_for(width, height))
