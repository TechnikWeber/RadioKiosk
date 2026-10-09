"""FM broadcast: tuning, presets and a band scan."""

import asyncio
import statistics

from ..config import load_json, save_json
from ..util import kill, spawn
from .receiver import Receiver

# one level measurement every 2.4 MHz covers the whole band
BAND_PROBES = [88.7e6 + i * 2.4e6 for i in range(9)]
SCAN_THRESHOLD_DB = 12


class Fm(Receiver):
    name = "fm"

    def __init__(self, core):
        super().__init__(core)
        self.stations = load_json("fm_stations.json", [])
        self.names = load_json("fm_names.json", {})   # "91.8" -> station name from RDS
        self.scanner = None
        self.mhz = None
        self.probing = False

    async def tune(self, mhz):
        mhz = round(min(108.0, max(87.5, float(mhz))), 2)
        async with self.core.lock:
            self.mhz = mhz
            name = self.names.get(f"{mhz:.1f}")
            title = f"{name} · {mhz:.2f} MHz" if name else f"{mhz:.2f} MHz"
            self.core.remember("fm", title, mhz=mhz)
            stereo = self.core.cfg["fm_stereo"]
            await self._receive(int(mhz * 1e6), "wfm", "fm", title, {"mhz": mhz, "stereo": stereo}, stereo=stereo)

    def on_rds(self, info):
        if self.probing or self.mhz is None:
            return
        if info.get("ps"):
            self._remember(self.mhz, info["ps"])
            self.core.update(title=f"{info['ps']} · {self.mhz:.2f} MHz")
        if info.get("text"):
            self.core.update(text=info["text"])

    def _remember(self, mhz, name):
        if self.names.get(f"{mhz:.1f}") != name:
            self.names[f"{mhz:.1f}"] = name
            save_json("fm_names.json", self.names)
        self.core.favorites.retitle(("fm", f"{mhz:.2f}"), f"{name} · {mhz:.2f} MHz")

    async def scan(self):
        await self.core.stop()
        async with self.core.lock:
            await self.core.take(self)
            self.core.update(source=self.name, status="loading", title="", text="", error=None,
                             detail={"scan": True})
            try:
                gain = await self.core.gains.get("fm", BAND_PROBES, remeasure=True)
                self.scanner = await spawn(
                    "rtl_power", "-f", "87.5M:108M:50k", "-i", "2", "-1", "-g", str(gain), "-",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                out, _ = await asyncio.wait_for(self.scanner.communicate(), 30)
                self.stations = self._find_stations(out.decode())
                save_json("fm_stations.json", self.stations)
                self.names = {}   # the same frequency is another station somewhere else
                save_json("fm_names.json", self.names)
                await self._name_stations()
            except (RuntimeError, asyncio.TimeoutError) as e:
                self.core.fail(str(e) or "scan timed out")
                return
            finally:
                await kill(self.scanner)
                self.scanner = None
                self.probing = False
                await self.backends["engine"].stop()
            self.core.active = None
            self.core.update(source=None, status="idle", detail={})

    async def _name_stations(self):
        """Listen to every found station for a moment to read its name from RDS."""
        engine = self.backends["engine"]
        if not engine.available():
            return
        self.probing = True
        await asyncio.sleep(0.5)   # let rtl_power release the stick
        for station in self.stations:
            self.core.update(detail={"scan": True, "naming": station["mhz"]})
            name = await engine.probe(int(station["mhz"] * 1e6), 5)
            if name:
                self._remember(station["mhz"], name)

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

    async def stop(self):
        await kill(self.scanner)
        self.mhz = None
        await super().stop()
