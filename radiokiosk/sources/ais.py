"""Ships (AIS on 162 MHz) through rtl_ais, which prints one NMEA sentence per message.

The decoding of those sentences is done here: position reports of large and
small vessels (types 1-3, 18, 19) and their names (types 5, 24).
"""

import asyncio
import shutil
import time

from ..util import kill, spawn

FORGET_AFTER = 900   # seconds; ships at anchor report every three minutes


def bits_of(payload, fill=0):
    """The payload of an AIVDM sentence as a string of bits: every character carries six."""
    out = []
    for ch in payload:
        value = ord(ch) - 48
        if value > 40:
            value -= 8
        out.append(format(value & 63, "06b"))
    bits = "".join(out)
    return bits[:len(bits) - fill] if fill else bits


def _number(bits, start, end, signed=False):
    chunk = bits[start:end]
    if len(chunk) < end - start:
        raise ValueError("message too short")
    value = int(chunk, 2)
    return value - (1 << (end - start)) if signed and chunk[0] == "1" else value


def _text(bits, start, end):
    chars = []
    for i in range(start, min(end, len(bits) - 5), 6):
        value = int(bits[i:i + 6], 2)
        chars.append(chr(value + 64 if value < 32 else value))
    return "".join(chars).replace("@", " ").strip()


def decode(bits):
    """What one AIS message says about a ship; None for message types that say nothing we show."""
    try:
        kind = _number(bits, 0, 6)
        ship = {"mmsi": _number(bits, 8, 38)}
        if kind in (1, 2, 3):
            fields = (50, 61, 89, 116, 128)
        elif kind == 18:
            fields = (46, 57, 85, 112, 124)
        elif kind == 19:
            fields = (46, 57, 85, 112, 124)
            ship["name"] = _text(bits, 143, 263)
        elif kind == 5:
            ship.update(name=_text(bits, 112, 232), kind=_number(bits, 232, 240), destination=_text(bits, 302, 422))
            return ship
        elif kind == 24 and _number(bits, 38, 40) == 0:
            ship["name"] = _text(bits, 40, 160)
            return ship
        else:
            return None
        speed, lon, lat, course, heading = fields
        knots, track = _number(bits, speed, speed + 10), _number(bits, course, course + 12)
        east, north = _number(bits, lon, lon + 28, True) / 600000, _number(bits, lat, lat + 27, True) / 600000
        if abs(east) <= 180 and abs(north) <= 90:   # 181 and 91 mean "not available"
            ship.update(lon=round(east, 5), lat=round(north, 5))
        if knots < 1023:
            ship["speed"] = knots / 10
        if track < 3600:
            ship["track"] = track / 10
        return ship
    except ValueError:
        return None


class Sentences:
    """Puts messages back together that were split over several NMEA sentences."""

    def __init__(self):
        self.parts = {}

    def feed(self, line):
        """Bits of a complete message, or None while parts are missing or the line is something else."""
        fields = line.strip().split(",")
        if len(fields) < 7 or fields[0] not in ("!AIVDM", "!AIVDO"):
            return None
        try:
            total, number, fill = int(fields[1]), int(fields[2]), int(fields[6][:1] or 0)
        except ValueError:
            return None
        if total == 1:
            return bits_of(fields[5], fill)
        key = (fields[3], fields[4])
        if number == 1:
            self.parts[key] = []
        if key not in self.parts or len(self.parts[key]) != number - 1:
            self.parts.pop(key, None)
            return None
        self.parts[key].append(bits_of(fields[5], fill))
        if number == total:
            return "".join(self.parts.pop(key))
        return None


class Ais:
    name = "ais"

    def __init__(self, core):
        self.core = core
        self.proc = None
        self.reader = None
        self.ships = {}

    @staticmethod
    def available():
        return shutil.which("rtl_ais") is not None

    async def start(self):
        if not self.available():
            raise RuntimeError("rtl_ais is not installed")
        self.core.need_sdr()
        await self.core.stop()
        async with self.core.lock:
            await self.core.take(self)
            self.ships = {}
            self.core.update(source=self.name, status="loading", title="AIS", text="", error=None, detail={})
            # -n prints the sentences, on stderr; a gain near the top suits the weak signals of distant ships
            self.proc = await spawn("rtl_ais", "-n", "-g", "40",
                                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
            self.reader = asyncio.create_task(self._run(self.proc))

    async def _run(self, proc):
        sentences = Sentences()
        self.core.update(status="playing")
        while line := await proc.stderr.readline():
            bits = sentences.feed(line.decode(errors="replace"))
            ship = decode(bits) if bits else None
            if ship:
                self.ships[ship["mmsi"]] = {**self.ships.get(ship["mmsi"], {}), **ship, "seen": time.time()}
        if proc is self.proc:
            self.core.fail("rtl_ais could not open the SDR stick")

    def list(self):
        limit = time.time() - FORGET_AFTER
        self.ships = {k: s for k, s in self.ships.items() if s["seen"] >= limit}
        return [{**s, "seen": round(time.time() - s["seen"])} for s in self.ships.values()]

    def on_title(self, title):
        pass

    async def stop(self):
        if self.reader:
            self.reader.cancel()
        proc, self.proc = self.proc, None
        await kill(proc)
