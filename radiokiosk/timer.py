"""Kitchen timer: counts down in the service, so it rings whatever the screen shows.

The tone comes from a player of its own and lies over the station that is
playing, instead of replacing it.
"""

import asyncio
import shutil
import time

from .util import kill, spawn

RING_FOR = 60   # seconds, unless somebody stops it earlier
TONE = "av://lavfi:sine=frequency=880:beep_factor=2:duration=%d" % RING_FOR


class Timer:
    def __init__(self, core):
        self.core = core
        self.task = None
        self.player = None
        core.state["timer"] = {"until": None, "ringing": False}

    async def set(self, seconds):
        """Start a countdown; 0 stops it, also while it rings."""
        if self.task:
            self.task.cancel()
            self.task = None
        player, self.player = self.player, None
        await kill(player)
        self.core.update(timer={"until": time.time() + seconds if seconds else None, "ringing": False})
        if seconds:
            self.task = asyncio.create_task(self._run(seconds))

    async def _run(self, seconds):
        await asyncio.sleep(seconds)
        self.core.update(timer={"until": None, "ringing": True})
        if shutil.which("mpv"):
            self.player = await spawn("mpv", "--no-video", "--no-terminal", "--no-config", TONE,
                                      stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.sleep(RING_FOR)
        self.task = None
        await self.set(0)
