"""Pictures from a folder, as a slide show for the gallery tile and the idle screen.

The folder may be anything the computer can read: a local folder, a USB stick,
or a network share the user has mounted. Photos are scaled down to screen size
once and kept in the cache, so a small computer does not decode twelve megapixels
for every slide.

Nothing here knows about radio; the module stands on its own.
"""

import hashlib
import io
import os
import re
import subprocess
import time
from pathlib import Path

from .config import CACHE_DIR, WEB_DIR

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:   # without Pillow the pictures go out as they are
    Image = None

KINDS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
# fit: "whole" shows all of a picture, "fill" crops it to the screen, "smart" crops only where little is lost
DEFAULTS = {"folder": None, "seconds": 15, "shuffle": True, "fit": "whole", "subfolders": True, "effect": "fade", "pan": "up", "pan_range": 80}
FITS = ("whole", "smart", "fill")
PANS = ("up", "down", "off")   # a picture cropped to the screen travels from its lower end to its upper, or the other way
PAN_RANGES = (50, 80, 100)     # per cent of the way the pan covers; less is slower and leaves the ends unvisited
EFFECTS = ("fade", "slide", "flip", "zoom", "mix")   # how one picture gives way to the next; "mix" takes them in turn
DEMO = WEB_DIR.parent / "demo-pictures"   # shown until a folder is chosen
SECONDS = (5, 10, 15, 30, 60, 300)
LIMIT = 5000              # pictures taken from one folder
RESCAN_AFTER = 120        # seconds a list of pictures is trusted
SIZES = (320, 960, 1600, 2560)  # longest edge a picture is scaled to; the smallest that fills the screen (or a thumbnail) is used
MAX_UPLOAD = 40 * 1024 * 1024   # bytes one uploaded picture may have
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


def backdrop(path):
    """What lies behind a picture that does not fill the screen: the picture itself, small, blurred and
    darkened, for the interface to stretch over the screen. Made once and cached, so a small computer
    does not have to blur anything while the pictures change. None without Pillow or for no picture."""
    small = scaled(path, SIZES[0])
    if small is None or Image is None:
        return None
    target = small.with_name(small.stem + "-back.jpg")
    if target.exists():
        return target
    try:
        with Image.open(small) as picture:
            picture = picture.convert("RGB").filter(ImageFilter.GaussianBlur(14))
            partial = target.with_suffix(".part")
            ImageEnhance.Brightness(picture).enhance(0.55).save(partial, "JPEG", quality=75)
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


def own_folder():
    """Where pictures uploaded through the interface go while no folder was chosen: Pictures/RadioKiosk."""
    try:
        out = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    return Path(out if out and out != str(Path.home()) else Path.home() / "Pictures") / "RadioKiosk"


def safe_name(name):
    """A file name from another device, made harmless: no folders in it, no odd characters."""
    name = re.sub(r"[^\w.\- ]", "_", Path(str(name).replace("\\", "/")).name).strip(" .")
    if not name or not is_picture(Path(name)):
        raise ValueError("this is not a picture")
    return name[-120:]


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
        if key == "pan" and value in PANS:
            return value
        if key == "pan_range" and value in PAN_RANGES:
            return value
        if key == "effect" and value in EFFECTS:
            return value
        raise ValueError("unknown setting")

    def listing(self):
        """Every picture with its number in the slide show and its path below the folder."""
        self.refresh(True)
        folder = Path(self.settings["folder"] or DEMO)
        return [{"index": i, "name": str(p.relative_to(folder))} for i, p in enumerate(self.pictures)]

    def add(self, name, data):
        """Keep an uploaded picture. Returns the folder it went to, which is a new one of the user's
        own while the demo pictures were still showing."""
        name = safe_name(name)
        if len(data) > MAX_UPLOAD:
            raise ValueError("this picture is too large")
        if Image is not None:
            try:
                with Image.open(io.BytesIO(data)) as picture:
                    picture.verify()
            except Exception:   # Pillow raises many kinds for what is no picture
                raise ValueError("this is not a picture")
        folder = Path(self.settings["folder"] or own_folder())
        folder.mkdir(parents=True, exist_ok=True)
        target, count = folder / name, 1
        while target.exists():   # never over a picture that is there already
            count += 1
            target = folder / f"{Path(name).stem}-{count}{Path(name).suffix}"
        partial = target.with_name(target.name + ".part")
        partial.write_bytes(data)
        partial.replace(target)
        return str(folder)

    def remove(self, name):
        """Delete one picture of the chosen folder, named by its path below it."""
        if not self.settings["folder"]:
            raise ValueError("the demo pictures belong to RadioKiosk and stay")
        folder = Path(self.settings["folder"]).resolve()
        target = (folder / str(name)).resolve()
        if folder not in target.parents or not is_picture(target) or not target.is_file():
            raise ValueError("this is not a picture of the gallery")
        target.unlink()
        self.refresh(True)

    def picture(self, index, width, height, back=False):
        """File to send for picture number `index`, or for the blurred backdrop behind it; the numbers wrap around."""
        self.refresh()
        if not self.pictures:
            return None
        path = self.pictures[index % len(self.pictures)]
        return backdrop(path) if back else scaled(path, box_for(width, height))
