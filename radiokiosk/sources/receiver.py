"""Sources that listen on the SDR stick, with two interchangeable backends.

"engine" is RadioKiosk's own receiver (waterfall, stereo, RDS, retunes on the
fly); "rtl_fm" is the classic command line program. Which one a source uses
is a setting, so both can be compared on the same station. The default "auto"
takes the own receiver where the processor is fast enough for it.
"""

import asyncio
import json
import struct
import sys
from pathlib import Path

from aiohttp import web

from .. import rtlsdr
from ..util import kill, spawn
from .rtlfm import RtlFmBackend

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
MPV_OPTIONS = ("demuxer=rawaudio,demuxer-rawaudio-format=s16le,demuxer-rawaudio-rate=48000,"
               "demuxer-rawaudio-channels=stereo,cache=no")
SNR_OFFSET = struct.calcsize("<dddf")     # positions inside a spectrum header
GAIN_OFFSET = struct.calcsize("<dddff")
SILENT_FOR = 10   # seconds without any output before the stick counts as hung


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
        self.wide = False     # the profile the running engine was started with
        self.snr = 0.0        # signal above noise in dB, as the engine last reported it
        self.frames = 0

    @staticmethod
    def available():
        return rtlsdr.available()

    def running(self):
        return self.proc is not None and self.proc.returncode is None

    async def _start(self, gain_key, wide=False):
        gains = self.core.gains
        self.wide = wide
        self.proc = await spawn(
            sys.executable, "-m", "radiokiosk.engine", "--gain", str(gains.known(gain_key, 28.0)),
            *(["--fixed-gain"] if gains.forced is not None else []), *(["--wide"] if wide else []),
            cwd=PROJECT_DIR, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
        self.audio = asyncio.Queue(maxsize=200)
        self.frames = 0
        asyncio.create_task(self._pump(self.proc, self.audio))
        asyncio.create_task(self._watch(self.proc))

    async def _watch(self, proc):
        """A hung stick blocks the engine without any error; notice the silence."""
        await asyncio.sleep(SILENT_FOR)
        if proc is self.proc and proc.returncode is None and self.frames == 0:
            self.proc = None
            proc.kill()
            self.core.fail("the SDR stick does not respond")

    def _tune(self, hz, mode, squelch=0, zoom=1, stereo="auto"):
        if hz != self.tuned:
            self.rds = {}
        self.tuned = hz
        command = {"hz": hz, "mode": mode, "squelch": squelch, "zoom": zoom, "stereo": stereo}
        self.proc.stdin.write(json.dumps(command).encode() + b"\n")

    async def receive(self, hz, mode, gain_key, title, detail, squelch=0, zoom=1, stereo="auto", wide=False):
        self.gain_key = gain_key
        name = self.owner.name
        if self.running() and wide != self.wide:
            await self.stop()   # the waterfall was switched: the engine needs its other profile
        if self.running():
            # the engine retunes on the fly, playback just continues
            same = hz == self.tuned
            self.core.update(source=name, title=title, error=None, detail=detail, **({} if same else {"text": ""}))
            self._tune(hz, mode, squelch, zoom, stereo)
            return
        self.core.update(source=name, status="loading", title=title, text="", error=None, detail=detail)
        await self._start(gain_key, wide)
        self._tune(hz, mode, squelch, zoom, stereo)
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
                    self.frames += 1
                    if audio.full():
                        audio.get_nowait()
                    audio.put_nowait(payload)
                elif head[:1] == b"S":
                    self.snr = struct.unpack_from("<f", payload, SNR_OFFSET)[0]
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
CHOICES = ("auto", *BACKENDS)
# Share of one processor core the engine's light profile may take for "auto" to pick it.
# A Raspberry Pi 3 measures 0.6 here and keeps pace with a real station.
ENGINE_LOAD_LIMIT = 0.75
_load = None


def engine_fits():
    """Is this processor fast enough for the own receiver? Measured once, in its light profile."""
    global _load
    if _load is None:
        try:
            from .. import engine
            engine.load()                 # first run warms up
            _load = engine.load()
        except ImportError:
            _load = float("inf")
    return _load <= ENGINE_LOAD_LIMIT


def engine_load():
    """Share of one processor core the own receiver takes here; None where it cannot run."""
    engine_fits()
    return None if _load == float("inf") else _load


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
        wanted = self.core.cfg.get(f"{self.name}_backend", "auto")
        usable = available_backends()
        if wanted == "auto":
            wanted = "engine" if usable["engine"] and engine_fits() else "rtl_fm"
        return wanted if usable.get(wanted) else next((n for n, ok in usable.items() if ok), wanted)

    async def _receive(self, hz, mode, gain_key, title, detail, squelch=0, zoom=1, stereo="auto", wide=False):
        self.core.need_sdr()
        """Caller holds core.lock."""
        await self.core.take(self)
        backend = self.backends[self.backend_id()]
        if self.active is not None and self.active is not backend:
            await self.active.stop()
        self.active = backend
        await backend.receive(hz, mode, gain_key, title, detail, squelch, zoom, stereo, wide)

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
