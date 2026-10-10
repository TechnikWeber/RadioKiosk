"""APRS: positions that radio amateurs send by packet radio on 144.800 MHz, on a map.

rtl_fm listens on the frequency, direwolf turns the modem tones into packets.
What a packet says about a position is read here: the plain format, the
compressed one and Mic-E, which between them carry nearly every position on the air.
"""

import asyncio
import os
import re
import shutil
import time

from ..config import RUNTIME_DIR
from ..util import kill, spawn

FORGET_AFTER = 3600   # seconds; fixed stations report every half hour
FREQUENCIES = {"US": 144.39, "CA": 144.39, "AU": 145.175, "NZ": 144.575, "JP": 144.64}   # everyone else: 144.800
PLAIN = re.compile(r"(\d{2})(\d{2}\.\d{2})([NS])(.)(\d{3})(\d{2}\.\d{2})([EW])(.)")


def _base91(text):
    value = 0
    for ch in text:
        value = value * 91 + ord(ch) - 33
    return value


def _mic_e(destination, info):
    """Mic-E hides the latitude in the destination address and the longitude in three bytes."""
    if len(destination) < 6 or len(info) < 9:
        return None
    digits = ""
    for ch in destination[:6]:
        if ch.isdigit():
            digits += ch
        elif "A" <= ch <= "J":
            digits += str(ord(ch) - ord("A"))
        elif "P" <= ch <= "Y":
            digits += str(ord(ch) - ord("P"))
        elif ch in "KLZ":
            digits += "0"   # a blank: the position is deliberately vague
        else:
            return None
    lat = int(digits[:2]) + (int(digits[2:4]) + int(digits[4:6]) / 100) / 60
    if destination[3] < "P":
        lat = -lat
    degrees = ord(info[1]) - 28 + (100 if destination[4] >= "P" else 0)
    if 180 <= degrees <= 189:
        degrees -= 80
    elif 190 <= degrees <= 199:
        degrees -= 190
    minutes = ord(info[2]) - 28
    if minutes >= 60:
        minutes -= 60
    lon = degrees + (minutes + (ord(info[3]) - 28) / 100) / 60
    if destination[5] >= "P":
        lon = -lon
    return {"lat": round(lat, 5), "lon": round(lon, 5), "symbol": info[7], "comment": info[9:].strip()}


def position(destination, info):
    """Where a packet says its sender is: lat, lon, symbol and comment; None if it carries no position."""
    if not info:
        return None
    kind = info[0]
    try:
        if kind in "`'":
            return _mic_e(destination, info)
        if kind in "!=":
            body = info[1:]
        elif kind in "/@":
            body = info[8:]   # after a time stamp of seven characters
        else:
            return None
        plain = PLAIN.match(body)
        if plain:
            lat_deg, lat_min, north, _, lon_deg, lon_min, east, symbol = plain.groups()
            lat = (int(lat_deg) + float(lat_min) / 60) * (1 if north == "N" else -1)
            lon = (int(lon_deg) + float(lon_min) / 60) * (1 if east == "E" else -1)
            return {"lat": round(lat, 5), "lon": round(lon, 5), "symbol": symbol, "comment": body[plain.end():].strip()}
        if len(body) >= 13 and not body[0].isdigit():
            lat, lon = 90 - _base91(body[1:5]) / 380926, -180 + _base91(body[5:9]) / 190463
            if abs(lat) <= 90 and abs(lon) <= 180:
                return {"lat": round(lat, 5), "lon": round(lon, 5), "symbol": body[9], "comment": body[13:].strip()}
    except (ValueError, IndexError):
        pass
    return None


def packet(line):
    """One line of direwolf, "[0.3] DL1ABC-9>APRS,WIDE1-1:payload", as a station; None for anything else."""
    found = re.match(r"^\[[^\]]*\]\s+([A-Z0-9-]{3,9})>([A-Z0-9-]+)[^:]*:(.*)$", line.strip())
    if not found:
        return None
    sender, destination, info = found.groups()
    where = position(destination, info)
    return {"call": sender, **where} if where else None


class Aprs:
    name = "aprs"

    def __init__(self, core):
        self.core = core
        self.radio = None
        self.modem = None
        self.reader = None
        self.stations = {}

    @staticmethod
    def available():
        return shutil.which("direwolf") is not None and shutil.which("rtl_fm") is not None

    def mhz(self):
        return FREQUENCIES.get(self.core.cfg["country"].upper(), 144.8)

    async def start(self):
        if not self.available():
            raise RuntimeError("direwolf is not installed")
        self.core.need_sdr()
        await self.core.stop()
        async with self.core.lock:
            await self.core.take(self)
            self.core.update(source=self.name, status="loading", title="APRS", text=f"{self.mhz():.3f} MHz",
                             error=None, detail={})
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            settings = RUNTIME_DIR / "direwolf.conf"
            settings.write_text("ADEVICE stdin null\nCHANNEL 0\nMYCALL N0CALL\nMODEM 1200\n")
            source, sink = os.pipe()
            self.radio = await spawn("rtl_fm", "-f", f"{self.mhz()}M", "-s", "24000", "-g", str(self.core.gains.known("2m", 40)),
                                     "-", stdout=sink, stderr=asyncio.subprocess.DEVNULL)
            os.close(sink)
            self.modem = await spawn("direwolf", "-c", str(settings), "-r", "24000", "-D", "1", "-t", "0", "-q", "d", "-",
                                     stdin=source, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            os.close(source)
            self.reader = asyncio.create_task(self._run(self.modem))

    async def _run(self, modem):
        self.core.update(status="playing")
        while line := await modem.stdout.readline():
            station = packet(line.decode(errors="replace"))
            if station:
                self.stations[station["call"]] = {**station, "seen": time.time()}
        if modem is self.modem:
            self.core.fail("the APRS receiver stopped unexpectedly")

    def list(self):
        limit = time.time() - FORGET_AFTER
        self.stations = {k: s for k, s in self.stations.items() if s["seen"] >= limit}
        return [{**s, "seen": round(time.time() - s["seen"])} for s in self.stations.values()]

    def on_title(self, title):
        pass

    async def stop(self):
        if self.reader:
            self.reader.cancel()
        modem, self.modem = self.modem, None
        radio, self.radio = self.radio, None
        await kill(modem)
        await kill(radio)
