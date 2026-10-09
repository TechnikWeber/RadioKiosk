"""Sound over the network, both ways.

Out: /live.mp3 carries whatever this device is playing, for phones and
computers in the local network (when remote control is switched on).
In: AirPlay and Spotify Connect receivers, where their programs are installed.
"""

import asyncio
import shutil

from aiohttp import web

from .util import kill, spawn


def can_stream():
    return shutil.which("ffmpeg") is not None


async def live_stream(request):
    """One encoder per listener: simple, and there are only ever a few."""
    if not can_stream():
        raise web.HTTPNotFound()
    encoder = await spawn(
        "ffmpeg", "-loglevel", "quiet", "-f", "pulse", "-i", "@DEFAULT_MONITOR@", "-ac", "2",
        "-c:a", "libmp3lame", "-b:a", "160k", "-f", "mp3", "-",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    response = web.StreamResponse(headers={"Content-Type": "audio/mpeg", "Cache-Control": "no-cache"})
    await response.prepare(request)
    try:
        while chunk := await encoder.stdout.read(4096):
            await response.write(chunk)
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        await kill(encoder)
    return response


class Receivers:
    """Programs that let a phone play through this device; they run next to the radio."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.procs = {}

    def list(self):
        return [{"id": r["id"], "name": r["name"], "on": r["id"] in self.procs}
                for r in self.cfg["receivers"] if shutil.which(r["command"][0])]

    async def set(self, receiver_id, on):
        await kill(self.procs.pop(receiver_id, None))
        receiver = next((r for r in self.cfg["receivers"] if r["id"] == receiver_id), None)
        if on and receiver and shutil.which(receiver["command"][0]):
            self.procs[receiver_id] = await spawn(
                *receiver["command"], stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)

    async def start_enabled(self):
        for receiver_id in self.cfg["receivers_on"]:
            await self.set(receiver_id, True)

    async def close(self):
        for proc in self.procs.values():
            await kill(proc)
