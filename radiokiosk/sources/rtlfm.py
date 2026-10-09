"""Shared receiver for everything demodulated by rtl_fm.

rtl_fm writes raw PCM to stdout; the server exposes it as a local HTTP stream
so the shared mpv instance can play it.
"""

import asyncio

from aiohttp import web

from ..util import kill, sdr_devices

# rtl_fm arguments and output sample rate per mode. For wfm the stick samples at
# 5x the output rate: rtl_fm's resampler distorts on fractional ratios.
MODES = {
    "wfm": (["-M", "wbfm", "-s", "240000", "-r", "48000", "-E", "deemp", "-F", "9", "-A", "fast"], 48000),
    "nfm": (["-M", "fm", "-s", "24000", "-F", "9"], 24000),
    "am": (["-M", "am", "-s", "12000", "-E", "dc"], 12000),
    "usb": (["-M", "usb", "-s", "12000"], 12000),
    "lsb": (["-M", "lsb", "-s", "12000"], 12000),
}
# rtl_fm has no automatic volume for AM and sideband, so weak stations would be inaudible
LEVELLER = ",af=lavfi=[dynaudnorm=f=150:g=7:m=40:p=0.7]"
DIRECT_SAMPLING_BELOW = 24e6


class RtlFm:
    name = ""

    def __init__(self, core):
        self.core = core
        self.proc = None
        self.rate = 48000
        self.squelch = 0
        self.generation = 0

    async def _receive(self, hz, mode, gain_key, gain_frequencies, title, detail, squelch=0):
        """Caller holds core.lock."""
        await self.core.take(self)
        if self.proc is not None:
            await kill(self.proc)
            await asyncio.sleep(0.3)  # reopening the stick immediately can hang it
        self.core.update(source=self.name, status="loading", title=title, text="", error=None, detail=detail)
        args, self.rate = MODES[mode]
        args = ["rtl_fm", "-f", str(int(hz)), *args]
        devices = sdr_devices()
        if hz < DIRECT_SAMPLING_BELOW and devices and not devices[0]["v4"]:
            args += ["-E", "direct2"]   # bypasses the tuner, so its gain does not apply
        else:
            try:
                args += ["-g", str(await self.core.gains.get(gain_key, gain_frequencies))]
            except RuntimeError as e:
                self.core.fail(str(e))
                return
        self.squelch = squelch
        if squelch:
            args += ["-l", str(int(squelch))]
        self.proc = await asyncio.create_subprocess_exec(
            *args, "-", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        self.generation += 1
        options = ("demuxer=rawaudio,demuxer-rawaudio-format=s16le,"
                   f"demuxer-rawaudio-rate={self.rate},demuxer-rawaudio-channels=mono,cache=no")
        if mode in ("am", "usb", "lsb"):
            options += LEVELLER
        port = self.core.cfg["port"]
        await self.core.mpv.play(f"http://127.0.0.1:{port}/stream/{self.name}?g={self.generation}", options)

    async def stream(self, request):
        proc = self.proc
        if proc is None:
            raise web.HTTPNotFound()
        response = web.StreamResponse(headers={"Content-Type": "application/octet-stream"})
        await response.prepare(request)
        silence = bytes(self.rate // 10 * 2)
        sent = 0
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(proc.stdout.read(8192), 0.2)
                except asyncio.TimeoutError:
                    # a closed squelch makes rtl_fm write nothing; keep the player fed
                    chunk = silence if sent or self.squelch else b""
                    if proc.returncode is not None:
                        break
                else:
                    if not chunk:
                        break
                    sent += len(chunk)
                if chunk:
                    await response.write(chunk)
                elif proc is not self.proc:
                    break
        except (ConnectionError, asyncio.CancelledError):
            pass
        if not sent and proc is self.proc:
            self.core.fail("no data from the SDR stick – if this persists, replug it")
        return response

    def on_title(self, title):
        pass

    async def stop(self):
        await kill(self.proc)
        self.proc = None
