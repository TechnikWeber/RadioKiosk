"""FM broadcast: tuning, presets and a band scan."""

import asyncio
import statistics

from ..config import load_json, save_json
from .rtlfm import RtlFm

# one level measurement every 2.4 MHz covers the whole band
BAND_PROBES = [88.7e6 + i * 2.4e6 for i in range(9)]
SCAN_THRESHOLD_DB = 12


class Fm(RtlFm):
    name = "fm"

    def __init__(self, core):
        super().__init__(core)
        self.presets = load_json("fm_presets.json", [])
        self.stations = load_json("fm_stations.json", [])

    async def tune(self, mhz):
        mhz = round(min(108.0, max(87.5, float(mhz))), 2)
        async with self.core.lock:
            await self._receive(mhz * 1e6, "wfm", "fm", BAND_PROBES, f"{mhz:.2f} MHz", {"mhz": mhz})

    async def scan(self):
        await self.core.stop()
        async with self.core.lock:
            await self.core.take(self)
            self.core.update(source=self.name, status="loading", title="", text="", error=None,
                             detail={"scan": True})
            try:
                gain = await self.core.gains.get("fm", BAND_PROBES, remeasure=True)
                proc = await asyncio.create_subprocess_exec(
                    "rtl_power", "-f", "87.5M:108M:50k", "-i", "2", "-1", "-g", str(gain), "-",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                self.proc = proc
                out, _ = await asyncio.wait_for(proc.communicate(), 30)
                self.stations = self._find_stations(out.decode())
                save_json("fm_stations.json", self.stations)
            except (RuntimeError, asyncio.TimeoutError) as e:
                self.core.fail(str(e) or "scan timed out")
                return
            finally:
                self.proc = None
            self.core.active = None
            self.core.update(source=None, status="idle", detail={})

    @staticmethod
    def _find_stations(csv):
        """Local maxima on the 100 kHz channel grid that stand out of the noise floor."""
        power = {}
        for line in csv.splitlines():
            cells = line.split(",")
            if len(cells) < 7:
                continue
            low, step = float(cells[2]), float(cells[4])
            for i, value in enumerate(cells[6:]):
                channel = round((low + i * step) / 1e5)
                power[channel] = max(power.get(channel, -999.0), float(value))
        if not power:
            raise RuntimeError("no data from the SDR stick – if this persists, replug it")
        floor = statistics.median(power.values())
        found = []
        for channel, db in sorted(power.items()):
            near = [power.get(channel + d, -999.0) for d in (-2, -1, 1, 2)]
            if 875 <= channel <= 1080 and db - floor >= SCAN_THRESHOLD_DB and db >= max(near):
                found.append({"mhz": channel / 10, "level": round(db - floor)})
        return found

    def toggle_preset(self, mhz):
        mhz = round(float(mhz), 2)
        if mhz in self.presets:
            self.presets.remove(mhz)
        else:
            self.presets = sorted(self.presets + [mhz])
        save_json("fm_presets.json", self.presets)
        return self.presets
