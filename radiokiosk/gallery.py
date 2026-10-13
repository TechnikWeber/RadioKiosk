"""Pictures from a folder, as a slide show for the gallery tile and the idle screen.

The folder may be anything the computer can read: a local folder, a USB stick,
or a network share the user has mounted. Photos are scaled down to screen size
once and kept in the cache, so a small computer does not decode twelve megapixels
for every slide.

A video becomes a clip when it is added: its first half minute, without sound, small and
with few pictures a second, so that a small computer plays it in a loop like a picture that
moves. Clips lie in the folder beside the pictures and take their turn in the slide show.

Nothing here knows about radio; the module stands on its own.
"""

import hashlib
import io
import os
import re
import shutil
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
# What ffmpeg is asked to read. Phones, cameras, camcorders, old downloads: the ending only decides
# whether it is tried, ffmpeg looks into the file itself.
VIDEOS = {".mp4", ".m4v", ".mov", ".qt", ".mkv", ".webm", ".avi", ".wmv", ".asf", ".flv", ".f4v", ".3gp", ".3g2",
          ".mpg", ".mpeg", ".m2v", ".vob", ".ts", ".mts", ".m2ts", ".ogv", ".divx", ".dv", ".mxf"}
CLIP = ".clip.mp4"           # how a finished clip is named: holiday.mov becomes holiday.clip.mp4
CLIP_SECONDS = 30            # the most that is kept of a video; how long it is shown is the slide show's business
CLIP_EDGE = 960              # longest edge in pixels
CLIP_RATE = 20               # pictures a second
MAX_VIDEO = 2 * 1024 ** 3    # bytes one uploaded video may have
CONVERT_WITHIN = 30 * 60     # seconds a small computer gets for one video
UPLOADS = CACHE_DIR / "uploads"   # where a video waits until its clip is made


def is_picture(path):
    return path.suffix.lower() in KINDS and not path.name.startswith(".")


def is_clip(path):
    return path.name.lower().endswith(CLIP) and not path.name.startswith(".")


def is_slide(path):
    return is_picture(path) or is_clip(path)


def is_video(name):
    return Path(str(name)).suffix.lower() in VIDEOS


# How H.264 is written, by what this ffmpeg brings along. Fedora's own ffmpeg comes without x264 but with OpenH264.
ENCODERS = {"libx264": ["-profile:v", "main", "-preset", "veryfast", "-crf", "27"],
            "libopenh264": ["-b:v", "1500k"]}
found_encoder = []   # asked once


def encoder():
    """The H.264 encoder of this computer's ffmpeg, or None where there is no ffmpeg or none in it."""
    if not found_encoder:
        try:
            known = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20).stdout
        except (OSError, subprocess.SubprocessError):
            known = ""
        found_encoder.append(next((name for name in ENCODERS if f" {name} " in known), None))
    return found_encoder[0]


def can_convert():
    return encoder() is not None


def clip_command(source, target, codec="libx264"):
    """ffmpeg's call for one clip. H.264 plays everywhere and costs a small computer the least;
    a key frame every second lets the loop start again without a jerk."""
    fit = (f"scale=w='min({CLIP_EDGE},iw)':h='min({CLIP_EDGE},ih)':force_original_aspect_ratio=decrease"
           f":force_divisible_by=2,fps={CLIP_RATE},format=yuv420p")
    return ["nice", "-n", "15", "ffmpeg", "-v", "error", "-y", "-i", str(source), "-t", str(CLIP_SECONDS),
            "-map", "0:v:0", "-an", "-sn", "-dn", "-map_metadata", "-1", "-vf", fit,
            "-c:v", codec, *ENCODERS[codec], "-g", str(CLIP_RATE),
            "-threads", "2", "-movflags", "+faststart", "-f", "mp4", str(target)]


def poster(path):
    """The first picture of a clip as a cached JPEG: its thumbnail, and what lies blurred behind it."""
    try:
        stat = path.stat()
    except OSError:
        return None
    key = hashlib.sha1(f"{path}:{stat.st_mtime_ns}:{stat.st_size}:poster".encode()).hexdigest()
    target = SCALED / f"{key}.jpg"
    if target.exists():
        return target
    SCALED.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part.jpg")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-frames:v", "1", "-q:v", "4", str(partial)],
                       capture_output=True, timeout=60, check=True)
        partial.replace(target)
    except (OSError, subprocess.SubprocessError):
        partial.unlink(missing_ok=True)
        return None
    return target


def find_pictures(folder, deep=True):
    """The pictures and clips in a folder, with `deep` also those below it, sorted by path. Hidden folders are left out."""
    found = []
    for root, folders, files in os.walk(folder, followlinks=True):
        folders[:] = sorted(f for f in folders if not f.startswith(".")) if deep else []
        found += [Path(root) / name for name in sorted(files) if is_slide(Path(name))]
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
            "pictures": sum(1 for e in entries if is_slide(e) and e.is_file())}


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
                "demo": not folder, "start": folder or str(Path.home()), "places": places(),
                # which numbers of the slide show move, and whether this computer can make more of them
                "clips": [i for i, p in enumerate(self.pictures) if is_clip(p)], "video": can_convert()}

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
        return [{"index": i, "name": str(p.relative_to(folder)), "clip": is_clip(p)} for i, p in enumerate(self.pictures)]

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

    def add_video(self, name, source):
        """Make the clip of an uploaded video, which lies in the file `source`, and keep it with the
        pictures. Returns the folder it went to. The video itself is not kept."""
        if not can_convert():
            raise RuntimeError("ffmpeg is not installed")
        codec = encoder()
        stem = re.sub(r"[^\w.\- ]", "_", Path(str(name).replace("\\", "/")).stem).strip(" .")[-100:] or "video"
        folder = Path(self.settings["folder"] or own_folder())
        folder.mkdir(parents=True, exist_ok=True)
        target, count = folder / f"{stem}{CLIP}", 1
        while target.exists():
            count += 1
            target = folder / f"{stem}-{count}{CLIP}"
        partial = target.with_name(f".{target.name}.part")   # hidden, so the slide show never takes half a clip
        try:
            done = subprocess.run(clip_command(source, partial, codec), capture_output=True, timeout=CONVERT_WITHIN)
            if done.returncode or not partial.exists() or not partial.stat().st_size:
                raise ValueError("this video cannot be read")
            partial.replace(target)
        except subprocess.TimeoutExpired:
            raise ValueError("this video takes too long to convert")
        finally:
            partial.unlink(missing_ok=True)
        return str(folder)

    def remove(self, name):
        """Delete one picture of the chosen folder, named by its path below it."""
        if not self.settings["folder"]:
            raise ValueError("the demo pictures belong to RadioKiosk and stay")
        folder = Path(self.settings["folder"]).resolve()
        target = (folder / str(name)).resolve()
        if folder not in target.parents or not is_slide(target) or not target.is_file():
            raise ValueError("this is not a picture of the gallery")
        target.unlink()
        self.refresh(True)

    def picture(self, index, width, height, back=False):
        """File to send for picture number `index`, or for the blurred backdrop behind it; the numbers wrap around."""
        self.refresh()
        if not self.pictures:
            return None
        path = self.pictures[index % len(self.pictures)]
        if is_clip(path):   # as a picture a clip is its first one
            path = poster(path)
            if path is None:
                return None
        return backdrop(path) if back else scaled(path, box_for(width, height))

    def clip(self, index):
        """The file of clip number `index`, or None where that number is a picture."""
        self.refresh()
        if not self.pictures:
            return None
        path = self.pictures[index % len(self.pictures)]
        return path if is_clip(path) and path.is_file() else None
