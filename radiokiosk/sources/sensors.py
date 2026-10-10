"""Wireless sensors on 433.92 MHz: thermometers, weather stations, tyre pressure and more.

rtl_433 knows a few hundred of their protocols and prints one JSON line per
transmission; this source keeps the last reading of every sensor it hears.
"""

import asyncio
import json
import shutil
import time

from ..util import kill, spawn

FORGET_AFTER = 3600   # seconds; many sensors only report every few minutes
# what a reading may carry, under the names rtl_433 uses
VALUES = ("temperature_C", "humidity", "pressure_hPa", "wind_avg_km_h", "wind_max_km_h", "wind_dir_deg",
          "rain_mm", "battery_ok", "pressure_kPa", "light_lux", "uv", "moisture")


def reading(line):
    """One JSON line of rtl_433 as (key, sensor); None for anything else."""
    try:
        data = json.loads(line)
    except ValueError:
        return None
    if not isinstance(data, dict) or "model" not in data:
        return None
    if "temperature_C" not in data and "temperature_F" in data:
        data["temperature_C"] = round((data["temperature_F"] - 32) / 1.8, 1)
    if "wind_avg_km_h" not in data and "wind_avg_m_s" in data:
        data["wind_avg_km_h"] = round(data["wind_avg_m_s"] * 3.6, 1)
    sensor = {"model": str(data["model"]), "id": data.get("id"), "channel": data.get("channel"),
              **{key: data[key] for key in VALUES if isinstance(data.get(key), (int, float))}}
    return f'{sensor["model"]}/{sensor["id"]}/{sensor["channel"]}', sensor


class Sensors:
    name = "sensors"

    def __init__(self, core):
        self.core = core
        self.proc = None
        self.reader = None
        self.sensors = {}

    @staticmethod
    def available():
        return shutil.which("rtl_433") is not None

    async def start(self):
        if not self.available():
            raise RuntimeError("rtl_433 is not installed")
        await self.core.stop()
        async with self.core.lock:
            await self.core.take(self)
            self.core.update(source=self.name, status="loading", title="433 MHz", text="", error=None, detail={})
            self.proc = await spawn("rtl_433", "-F", "json", "-M", "level",
                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            self.reader = asyncio.create_task(self._run(self.proc))

    async def _run(self, proc):
        self.core.update(status="playing")
        while line := await proc.stdout.readline():
            found = reading(line.decode(errors="replace"))
            if found:
                key, sensor = found
                self.sensors[key] = {**sensor, "seen": time.time(), "count": self.sensors.get(key, {}).get("count", 0) + 1}
        if proc is self.proc:
            self.core.fail("rtl_433 could not open the SDR stick")

    def list(self):
        limit = time.time() - FORGET_AFTER
        self.sensors = {k: s for k, s in self.sensors.items() if s["seen"] >= limit}
        return sorted(({**s, "seen": round(time.time() - s["seen"])} for s in self.sensors.values()),
                      key=lambda s: s["seen"])

    def on_title(self, title):
        pass

    async def stop(self):
        if self.reader:
            self.reader.cancel()
        proc, self.proc = self.proc, None
        await kill(proc)
