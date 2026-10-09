"""Sources that listen on the SDR stick, with two interchangeable backends.

"engine" is RadioKiosk's own receiver (waterfall, stereo, RDS, retunes on the
fly); "rtl_fm" is the classic command line program. Which one a source uses
is a setting, so both can be compared on the same station.
"""

import asyncio
import json
import struct
import sys
from pathlib import Path

from aiohttp import web

from .. import rtlsdr
from ..util import kill
from .rtlfm import RtlFmBackend

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
MPV_OPTIONS = ("demuxer=rawaudio,demuxer-rawaudio-format=s16le,demuxer-rawaudio-rate=48000,"
               "demuxer-rawaudio-channels=stereo,cache=no")
GAIN_OFFSET = struct.calcsize("<dddff")   # position of the gain inside a spectrum header


class EngineBackend:
    """Runs the receiver engine as a subprocess and sorts its output:
    audio to mpv through a local HTTP stream, spectrum to the web interface."""
    id = "engine"

    def __init__(self, owner):
        self.owner = owner
        self.core = owner.core
        self.proc = None
        self.audio = None
        self.gain_key = None
        self.gain = None
        self.generation = 0
        self.rds = {}
        self.tuned = None

    @staticmethod
    def available():
        return rtlsdr.available()

    def running(self):
        return self.proc is not None and self.proc.returncode is None

    async def _start(self, gain_key):
        gains = self.core.gains
        self.proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "radiokiosk.engine", "--gain", str(gains.known(gain_key, 28.0)),
            *(["--fixed-gain"] if gains.forced is not None else []),
            cwd=PROJECT_DIR, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
        self.audio = asyncio.Queue(maxsize=200)
        asyncio.create_task(self._pump(self.proc, self.audio))

    def _tune(self, hz, mode, squelch=0, zoom=1):
        self.rds = {}
        self.tuned = hz
        command = {"hz": hz, "mode": mode, "squelch": squelch, "zoom": zoom}
        self.proc.stdin.write(json.dumps(command).encode() + b"\n")

    async def receive(self, hz, mode, gain_key, title, detail, squelch=0, zoom=1):
        self.gain_key = gain_key
        name = self.owner.name
        if self.running():
            # the engine retunes on the fly, playback just continues
            self.core.update(source=name, title=title, text="", error=None, detail=detail)
            self._tune(hz, mode, squelch, zoom)
            return
        self.core.update(source=name, status="loading", title=title, text="", error=None, detail=detail)
        await self._start(gain_key)
        self._tune(hz, mode, squelch, zoom)
        self.generation += 1
        port = self.core.cfg["port"]
        await self.core.mpv.play(f"http://127.0.0.1:{port}/stream/{name}?g={self.generation}", MPV_OPTIONS)

    async def probe(self, hz, seconds):
        """Listen silently for a station name; used by the FM scan."""
        if not self.running():
            await self._start("fm")
        self._tune(hz, "wfm")
        for _ in range(int(seconds * 10)):
            await asyncio.sleep(0.1)
            if self.rds.get("ps"):
                return self.rds["ps"]
        return ""

    async def _pump(self, proc, audio):
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
                elif head[:1] == b"R":
                    info = json.loads(payload)
                    if info.pop("hz") == self.tuned:   # not a late message from the previous station
                        self.rds = info
                        self.owner.on_rds(info)
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

    async def stop(self):
        proc, self.proc = self.proc, None
        await kill(proc)
        # remember the gain the engine settled on as the starting point for next time
        if proc and self.gain and self.gain_key and self.core.gains.forced is None:
            self.core.gains.remember(self.gain_key, round(self.gain, 1))


BACKENDS = {"engine": EngineBackend, "rtl_fm": RtlFmBackend}


def available_backends():
    return {name: backend.available() for name, backend in BACKENDS.items()}


class Receiver:
    name = ""

    def __init__(self, core):
        self.core = core
        self.backends = {name: backend(self) for name, backend in BACKENDS.items()}
        self.active = None

    def backend_id(self):
        """The backend chosen in the settings, or whichever one is installed."""
        wanted = self.core.cfg.get(f"{self.name}_backend", "engine")
        usable = available_backends()
        return wanted if usable.get(wanted) else next((n for n, ok in usable.items() if ok), wanted)

    async def _receive(self, hz, mode, gain_key, title, detail, squelch=0, zoom=1):
        """Caller holds core.lock."""
        await self.core.take(self)
        backend = self.backends[self.backend_id()]
        if self.active is not None and self.active is not backend:
            await self.active.stop()
        self.active = backend
        await backend.receive(hz, mode, gain_key, title, detail, squelch, zoom)

    async def stream(self, request):
        if self.active is None:
            raise web.HTTPNotFound()
        return await self.active.stream(request)

    def on_rds(self, info):
        pass

    def on_title(self, title):
        pass

    async def stop(self):
        active, self.active = self.active, None
        if active is not None:
            await active.stop()
