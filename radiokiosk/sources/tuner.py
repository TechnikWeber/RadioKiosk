"""Free listening on any frequency: band plan presets, favourites, manual tuning."""

import asyncio
import json
from pathlib import Path

from .receiver import Receiver

BANDS = json.loads((Path(__file__).resolve().parent.parent / "bands.json").read_text())


MODES = ("wfm", "nfm", "am", "usb", "lsb")


class Tuner(Receiver):
    name = "tuner"

    def __init__(self, core):
        super().__init__(core)
        self.scanner = None

    async def tune(self, hz, mode, squelch=0, zoom=1, label="", wide=False, scanning=False):
        hz = int(min(1.75e9, max(100e3, float(hz))))
        if mode not in MODES:
            raise RuntimeError("unknown mode")
        if not scanning:
            self._end_scan()   # tuning by hand takes over
        # signal levels differ a lot between bands, so the gain is remembered per 2 MHz slice
        gain_key = f"{hz // 2_000_000 * 2}MHz"
        async with self.core.lock:
            self.core.remember("tuner", label or self.format(hz), hz=hz, mode=mode, squelch=squelch)
            await self._receive(hz, mode, gain_key, label or self.format(hz),
                                {"hz": hz, "mode": mode, "squelch": squelch, "zoom": zoom, "scan": scanning},
                                squelch, zoom, wide=wide)

    async def scan(self, channels, mode, squelch, wide=False, seek=False, back=None):
        """Step through `channels` and stay wherever somebody is talking.

        With `seek` it is a station search instead: a broadcaster's carrier never goes away, so the scan
        ends on the first channel that has one, or on `back` after one round without."""
        if self.backend_id() != "engine":
            raise RuntimeError("the scan needs the own receiver")
        if not channels or len(channels) > 400:
            raise RuntimeError("nothing to scan")
        self._end_scan()
        self.scanner = asyncio.create_task(self._scan([int(c) for c in channels], mode, squelch or 6, wide,
                                                      seek, back or channels[-1]))

    async def _scan(self, channels, mode, squelch, wide, seek=False, back=None):
        engine = self.backends["engine"]
        while True:
            for hz in channels:
                await self.tune(hz, mode, squelch, 1, "", wide, scanning=True)
                await asyncio.sleep(0.4)    # the engine needs a few spectrum lines on the new channel
                if seek:
                    if engine.snr >= squelch:
                        await asyncio.sleep(0.4)   # a second look: the gain settling can pass for a signal
                        if engine.snr >= squelch:
                            return await self.tune(hz, mode, 0, 1, "", wide)
                    if self.core.active is not self:
                        return
                    continue
                gone = None   # seconds since the signal went away; None while nothing was heard
                while True:
                    if engine.snr >= squelch:
                        gone = 0.0
                    elif gone is None:
                        break            # empty channel: move on
                    else:
                        gone += 0.25
                        if gone >= 3:    # stay until 3 s after the last word
                            break
                    await asyncio.sleep(0.25)
                if self.core.active is not self:
                    return
            if seek:
                return await self.tune(back, mode, 0, 1, "", wide)   # nothing on the whole band

    def _end_scan(self):
        if self.scanner and self.scanner is not asyncio.current_task():
            self.scanner.cancel()
        self.scanner = None

    async def stop(self):
        self._end_scan()
        await super().stop()

    @staticmethod
    def format(hz):
        return f"{hz / 1e3:,.1f} kHz".replace(",", " ") if hz < 30e6 else f"{hz / 1e6:.4f} MHz"
