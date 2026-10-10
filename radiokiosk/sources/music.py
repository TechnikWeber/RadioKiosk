"""The own music collection: play the files of a folder, one after the other.

The folder is a setting; without one it is the system's music folder. As with
the gallery it may be a USB stick or a network share the user has mounted.
"""

import asyncio
import random
import subprocess
from pathlib import Path

AUDIO = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".wma"}
QUEUE = 500   # files handed to the player at once


def music_home():
    try:
        out = subprocess.run(["xdg-user-dir", "MUSIC"], capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    return Path(out if out and out != str(Path.home()) else Path.home() / "Music")


class Music:
    name = "music"

    def __init__(self, core):
        self.core = core
        self.watch = None

    def root(self):
        return Path(self.core.cfg["music_folder"] or music_home())

    def _inside(self, relative):
        """A path below the music folder; nothing above it can be reached through the interface."""
        root = self.root().resolve()
        target = (root / (relative or "")).resolve()
        if target != root and root not in target.parents:
            raise ValueError("outside the music folder")
        return root, target

    def listing(self, relative=""):
        root, folder = self._inside(relative)
        try:
            entries = sorted(folder.iterdir(), key=lambda e: e.name.lower())
        except OSError:
            return {"root": str(root), "path": "", "parent": None, "folders": [], "files": [], "missing": True}
        visible = [e for e in entries if not e.name.startswith(".")]
        return {"root": str(root), "path": str(folder.relative_to(root)) if folder != root else "",
                "parent": None if folder == root else (str(folder.parent.relative_to(root)) if folder.parent != root else ""),
                "folders": [e.name for e in visible if e.is_dir()],
                "files": [e.name for e in visible if e.is_file() and e.suffix.lower() in AUDIO], "missing": False}

    async def play(self, relative, name=None, shuffle=False):
        """Play a folder, starting with `name`; shuffled, the order is random and `name` comes first."""
        root, folder = self._inside(relative)
        files = self.listing(relative)["files"]
        if not files:
            raise RuntimeError("there is no music in this folder")
        if shuffle:
            random.shuffle(files)
            if name in files:
                files.insert(0, files.pop(files.index(name)))
        elif name in files:
            files = files[files.index(name):]
        queue = [str(folder / f) for f in files[:QUEUE]]
        async with self.core.lock:
            await self.core.take(self)
            self._end_watch()
            self.core.update(source=self.name, status="loading", title=folder.name or root.name, text=Path(queue[0]).stem,
                             error=None, detail={"path": relative or "", "file": Path(queue[0]).name})
            self.core.remember("music", folder.name or root.name, path=relative or "")
            try:
                await self.core.mpv.play(queue[0])
                for later in queue[1:]:
                    await self.core.mpv.command("loadfile", later, "append")
            except (RuntimeError, OSError) as e:
                self.core.fail(str(e))
                return
            self.watch = asyncio.create_task(self._watch())

    async def _watch(self):
        """End the source when the last file is over."""
        started = False
        while True:
            await asyncio.sleep(3)
            try:
                idle = (await self.core.mpv.command("get_property", "idle-active")).get("data")
                name = (await self.core.mpv.command("get_property", "filename")).get("data")
            except (RuntimeError, asyncio.TimeoutError):
                continue
            if name:
                started = True
                self.core.update(detail={**self.core.state["detail"], "file": name})
            if idle and started:
                asyncio.create_task(self.core.stop())
                return

    async def skip(self, step):
        if self.core.active is self:
            await self.core.mpv.command("playlist-next" if step > 0 else "playlist-prev", "weak")

    def on_title(self, title):
        if title:
            self.core.update(text=title)

    def _end_watch(self):
        if self.watch and not self.watch.done() and self.watch is not asyncio.current_task():
            self.watch.cancel()
        self.watch = None

    async def stop(self):
        self._end_watch()
