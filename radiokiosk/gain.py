"""Tuner gain per band.

The stick's own automatic gain overdrives its ADC on a good antenna (heavy
noise and distortion), and one fixed value cannot fit every antenna and band.
The receiver engine therefore adjusts the gain itself while it runs; this
module measures it for programs that cannot (band scan, SDR++) and remembers
the result per band.
"""

import asyncio
import math

from .config import load_json, save_json

# gain steps of the R820T/R828D tuner in dB
TUNER_GAINS = [0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7, 16.6, 19.7, 20.7, 22.9, 25.4,
               28.0, 29.7, 32.8, 33.8, 36.4, 37.2, 38.6, 40.2, 42.1, 43.4, 43.9, 44.5, 48.0, 49.6]
TARGET_RMS = 16.0   # of 127; about 18 dB below full scale
PROBE_GAIN = 20.7


async def _measure(hz, gain):
    """RMS level and clipped fraction of the raw 8-bit samples around `hz`."""
    proc = await asyncio.create_subprocess_exec(
        "rtl_sdr", "-f", str(int(hz)), "-s", "2400000", "-g", str(gain), "-n", "960000", "-",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    data, _ = await proc.communicate()
    data = data[len(data) // 2:]   # the tuner needs a moment to settle
    if len(data) < 10000:
        raise RuntimeError("no data from the SDR stick – if this persists, replug it")
    clipped = (data.count(0) + data.count(255)) / len(data)
    sample = data[::16]
    rms = math.sqrt(sum((b - 127.5) ** 2 for b in sample) / len(sample))
    return rms, clipped


async def calibrate(frequencies):
    """Highest gain that keeps every listed frequency at or below the target level."""
    best = TUNER_GAINS[-1]
    for hz in frequencies:
        gain = PROBE_GAIN
        rms, clipped = await _measure(hz, gain)
        if clipped > 0.005:
            gain = 3.7
            rms, _ = await _measure(hz, gain)
        wanted = gain + 20 * math.log10(TARGET_RMS / max(rms, 0.5))
        best = min(best, max((g for g in TUNER_GAINS if g <= wanted), default=TUNER_GAINS[0]))
    return best


class Gains:
    def __init__(self, cfg):
        self.forced = cfg["gain"] if isinstance(cfg["gain"], (int, float)) else None
        self.cache = load_json("gains.json", {})

    def known(self, key, default):
        return self.forced if self.forced is not None else self.cache.get(key, default)

    async def get(self, key, frequencies, remeasure=False):
        """Gain for the band `key`; measures on first use. The SDR must be free."""
        if self.forced is not None:
            return self.forced
        if key not in self.cache or remeasure:
            self.cache[key] = await calibrate(frequencies)
            save_json("gains.json", self.cache)
        return self.cache[key]

    def remember(self, key, gain):
        if self.cache.get(key) != gain:
            self.cache[key] = gain
            save_json("gains.json", self.cache)

    def forget(self):
        self.cache = {}
        save_json("gains.json", self.cache)
