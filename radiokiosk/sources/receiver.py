"""Base for the sources that listen through the receiver engine.

The engine runs as a subprocess that holds the SDR stick. This class starts
it, forwards its audio to mpv through a local HTTP stream and its spectrum to
the web interface.
"""

import asyncio
import json
import struct
import sys
from pathlib import Path

from aiohttp import web

from ..util import kill

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
MPV_OPTIONS = ("demuxer=rawaudio,demuxer-rawaudio-format=s16le,demuxer-rawaudio-rate=48000,"
               "demuxer-rawaudio-channels=stereo,cache=no")
GAIN_OFFSET = struct.calcsize("<dddff")   # position of the gain inside a spectrum header


class Receiver:
    name = ""

    def __init__(self, core):
        self.core = core
        self.proc = None
        self.audio = None
        self.gain_key = None
        self.gain = None
        self.generation = 0

    def running(self):
        return self.proc is not None and self.proc.returncode is None

    async def _receive(self, hz, mode, gain_key, title, detail, squelch=0, zoom=1):
        """Caller holds core.lock."""
        await self.core.take(self)
        self.gain_key = gain_key
        command = json.dumps({"hz": hz, "mode": mode, "squelch": squelch, "zoom": zoom}).encode() + b"\n"
        if self.running():
            # the engine retunes on the fly, playback just continues
            self.core.update(source=self.name, title=title, text="", error=None, detail=detail)
            self.proc.stdin.write(command)
            return
        self.core.update(source=self.name, status="loading", title=title, text="", error=None, detail=detail)
        gains = self.core.gains
        self.proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "radiokiosk.engine", "--gain", str(gains.known(gain_key, 28.0)),
            *(["--fixed-gain"] if gains.forced is not None else []),
            cwd=PROJECT_DIR, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
        self.audio = asyncio.Queue(maxsize=200)
        self.proc.stdin.write(command)
        asyncio.create_task(self._pump(self.proc, self.audio))
        self.generation += 1
        port = self.core.cfg["port"]
        await self.core.mpv.play(f"http://127.0.0.1:{port}/stream/{self.name}?g={self.generation}", MPV_OPTIONS)

    async def _pump(self, proc, audio):
        """Sort the engine's output: audio to the player, spectrum to the browsers."""
        try:
            while True:
                head = await proc.stdout.readexactly(5)
                payload = await proc.stdout.readexactly(int.from_bytes(head[1:], "little"))
                if head[:1] == b"A":
                    if audio.full():
                        audio.get_nowait()
                    audio.put_nowait(payload)
                elif head[:1] == b"S":
                    self.gain = struct.unpack_from("<f", payload, GAIN_OFFSET)[0]
                    self.core.broadcast_bytes(payload)
                elif head[:1] == b"E":
                    self.core.fail(payload.decode())
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        if proc is self.proc and self.core.state["status"] != "error":
            self.core.fail("the receiver stopped unexpectedly")

    async def stream(self, request):
        proc, audio = self.proc, self.audio
        if proc is None:
            raise web.HTTPNotFound()
        response = web.StreamResponse(headers={"Content-Type": "application/octet-stream"})
        await response.prepare(request)
        try:
            while proc is self.proc and proc.returncode is None:
                try:
                    await response.write(await asyncio.wait_for(audio.get(), 1))
                except asyncio.TimeoutError:
                    continue
        except (ConnectionError, asyncio.CancelledError):
            pass
        return response

    def on_title(self, title):
        pass

    async def stop(self):
        proc, self.proc = self.proc, None
        await kill(proc)
        # remember the gain the engine settled on as the starting point for next time
        if self.gain and self.gain_key and self.core.gains.forced is None:
            self.core.gains.remember(self.gain_key, round(self.gain, 1))
