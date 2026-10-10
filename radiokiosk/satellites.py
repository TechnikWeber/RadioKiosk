"""When does a satellite come over? Passes of the ISS and of satellites worth listening to.

The orbits come from CelesTrak (free, no key) once or twice a day; the passes
are then worked out here, so they also come without a connection. The orbit
model itself is the standard one (SGP4), from the package python3-sgp4.
"""

import asyncio
import math
import time

import aiohttp
import numpy as np

from .config import load_json, save_json
from .feeds import HEADERS

try:
    from sgp4.api import Satrec
except ImportError:
    Satrec = None

ELEMENTS = "https://celestrak.org/NORAD/elements/gp.php"
GROUPS = ("stations", "amateur", "weather")
KEEP = 12 * 3600      # seconds; CelesTrak asks not to fetch more often than the orbits change
STEP = 20             # seconds between looks at the sky
LOWEST = 10           # degrees a pass must reach to be worth listing
# catalogue number -> name, what it sends on (MHz), how to listen
SATELLITES = {
    25544: ("ISS", 145.800, "nfm", "voice, SSTV; repeater on 437.800"),
    27607: ("SO-50", 436.795, "nfm", "FM repeater"),
    43017: ("AO-91", 145.960, "nfm", "FM repeater"),
    7530: ("AO-7", 145.950, "usb", "linear transponder"),
    44909: ("RS-44", 435.640, "usb", "linear transponder"),
    57166: ("Meteor-M N2-3", 137.900, "wfm", "weather pictures"),
    59051: ("Meteor-M N2-4", 137.900, "wfm", "weather pictures"),
}
EARTH, FLATTENING = 6378.137, 1 / 298.257223563


def available():
    return Satrec is not None


def parse_elements(text):
    """Catalogue number -> (line 1, line 2) for the satellites listed above."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    found = {}
    for first, second in zip(lines, lines[1:]):
        if first.startswith("1 ") and second.startswith("2 "):
            try:
                number = int(first[2:7])
            except ValueError:
                continue
            if number in SATELLITES:
                found[number] = (first, second)
    return found


def _observer(lat, lon):
    """Where the listener stands (km, fixed to the earth) and the directions up, east and north there."""
    lat, lon = math.radians(lat), math.radians(lon)
    squashed = (1 - FLATTENING) ** 2
    across = EARTH / math.sqrt(math.cos(lat) ** 2 + squashed * math.sin(lat) ** 2)
    place = np.array([across * math.cos(lat) * math.cos(lon), across * math.cos(lat) * math.sin(lon),
                      across * squashed * math.sin(lat)])
    up = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])
    east = np.array([-math.sin(lon), math.cos(lon), 0.0])
    north = np.array([-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat)])
    return place, up, east, north


def look_angles(lines, lat, lon, moments):
    """Elevation and azimuth in degrees of a satellite at the given unix times."""
    satellite = Satrec.twoline2rv(*lines)
    moments = np.asarray(moments, dtype=float)
    julian = moments / 86400.0 + 2440587.5
    whole = np.floor(julian)
    _, position, _ = satellite.sgp4_array(whole, julian - whole)
    # SGP4 answers in a frame that does not turn with the earth: turn it by the earth's angle
    centuries = (julian - 2451545.0) / 36525.0
    seconds = 67310.54841 + (876600 * 3600 + 8640184.812866) * centuries + 0.093104 * centuries ** 2 - 6.2e-6 * centuries ** 3
    angle = np.radians((seconds % 86400.0) / 240.0)
    x = np.cos(angle) * position[:, 0] + np.sin(angle) * position[:, 1]
    y = -np.sin(angle) * position[:, 0] + np.cos(angle) * position[:, 1]
    place, up, east, north = _observer(lat, lon)
    line_of_sight = np.column_stack([x, y, position[:, 2]]) - place
    distance = np.linalg.norm(line_of_sight, axis=1)
    elevation = np.degrees(np.arcsin((line_of_sight @ up) / distance))
    azimuth = np.degrees(np.arctan2(line_of_sight @ east, line_of_sight @ north)) % 360
    return elevation, azimuth


def passes(elements, lat, lon, start, hours=24):
    """The passes of the listed satellites within the next hours that rise high enough, in order of time."""
    moments = start + np.arange(0, hours * 3600, STEP)
    found = []
    for number, lines in elements.items():
        name, mhz, mode, note = SATELLITES[number]
        try:
            elevation, azimuth = look_angles(lines, lat, lon, moments)
        except (ValueError, RuntimeError):
            continue
        above = np.flatnonzero(np.nan_to_num(elevation, nan=-90.0) > 0)
        if not len(above):
            continue
        for run in np.split(above, np.flatnonzero(np.diff(above) > 1) + 1):
            top = run[np.argmax(elevation[run])]
            if elevation[top] < LOWEST:
                continue
            found.append({"number": number, "name": name, "mhz": mhz, "mode": mode, "note": note,
                          "rise": float(moments[run[0]]), "set": float(moments[run[-1]]) + STEP,
                          "highest": round(float(elevation[top])), "at": float(moments[top]),
                          "from": round(float(azimuth[run[0]])), "to": round(float(azimuth[run[-1]]))})
    return sorted(found, key=lambda p: p["rise"])


class Satellites:
    def __init__(self):
        self.stored = load_json("satellites.json", {"read": 0, "elements": {}})
        self.reading = None

    async def _read(self):
        found = {}
        try:
            async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=20)) as http:
                for group in GROUPS:
                    async with http.get(ELEMENTS, params={"GROUP": group, "FORMAT": "tle"}) as r:
                        r.raise_for_status()
                        found.update(parse_elements(await r.text()))
        except (aiohttp.ClientError, TimeoutError):
            pass
        if found:
            self.stored = {"read": time.time(), "elements": {str(k): list(v) for k, v in found.items()}}
            save_json("satellites.json", self.stored)

    async def get(self, location):
        if not available():
            raise RuntimeError("python3-sgp4 is not installed")
        if not location:
            raise RuntimeError("no location set")
        if time.time() - self.stored["read"] > KEEP:
            if self.reading is None or self.reading.done():
                self.reading = asyncio.create_task(self._read())
            if not self.stored["elements"]:   # nothing to work with yet: wait for the first orbits
                await self.reading
        if not self.stored["elements"]:
            raise RuntimeError("the satellites' orbits cannot be reached")
        elements = {int(k): tuple(v) for k, v in self.stored["elements"].items()}
        found = await asyncio.to_thread(passes, elements, location[0], location[1], time.time())
        return {"passes": found, "orbits_age": round((time.time() - self.stored["read"]) / 3600)}
