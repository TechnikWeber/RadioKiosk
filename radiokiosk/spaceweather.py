"""Propagation for radio amateurs: solar and geomagnetic figures, band conditions, MUF.

Two free sources, neither needs a key:
- hamqsl.com (Paul Herrman, N0NBH) for the figures and the calculated band conditions,
- prop.kc2g.com (Andrew Rodland, KC2G) for what the ionosondes of the GIRO network
  measure; the one nearest to the own location gives MUF and foF2.
"""

import calendar
import math
import time
import xml.etree.ElementTree as ET

import aiohttp

from .feeds import HEADERS

SOLAR_URL = "https://www.hamqsl.com/solarxml.php"
SONDES_URL = "https://prop.kc2g.com/api/stations.json"
KEEP = 15 * 60          # seconds; the sources themselves change every 15 minutes to 3 hours
SONDE_MAX_AGE = 3 * 3600


def parse_solar(data):
    """The figures of hamqsl's XML as a flat dictionary, plus the band conditions."""
    root = ET.fromstring(data).find("solardata")
    text = lambda name: (root.findtext(name) or "").strip()

    def number(name):
        try:
            return float(text(name))
        except ValueError:
            return None

    return {
        "updated": text("updated"), "flux": number("solarflux"), "sunspots": number("sunspots"),
        "a": number("aindex"), "k": number("kindex"), "xray": text("xray"), "wind": number("solarwind"),
        "bz": number("magneticfield"), "aurora": number("aurora"), "field": text("geomagfield"),
        "noise": text("signalnoise"),
        "bands": [{"band": b.get("name"), "time": b.get("time"), "state": (b.text or "").strip().lower()}
                  for b in root.iter("band")],
        "vhf": [{"name": p.get("name"), "where": p.get("location"), "state": (p.text or "").strip()}
                for p in root.iter("phenomenon")],
    }


def _km(a, b):
    (lat1, lon1), (lat2, lon2) = a, b
    rad = math.pi / 180
    h = (math.sin((lat2 - lat1) * rad / 2) ** 2
         + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin((lon2 - lon1) * rad / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))


def nearest_sonde(stations, location, now=None):
    """MUF and foF2 of the nearest ionosonde that reported recently; None if there is none."""
    now = now or time.time()
    best = None
    for s in stations:
        try:
            place = (float(s["station"]["latitude"]), (float(s["station"]["longitude"]) + 180) % 360 - 180)
            age = now - calendar.timegm(time.strptime(s["time"][:19], "%Y-%m-%dT%H:%M:%S"))
        except (KeyError, TypeError, ValueError):
            continue
        if s.get("mufd") is None or not 0 <= age <= SONDE_MAX_AGE:
            continue
        distance = _km(location, place)
        if best is None or distance < best["km"]:
            best = {"name": s["station"]["name"], "km": round(distance), "muf": round(s["mufd"], 1),
                    "fof2": s.get("fof2"), "age": round(age / 60)}
    return best


class SpaceWeather:
    def __init__(self):
        self.cached = None
        self.cached_for = None
        self.fetched = 0

    async def get(self, location):
        if self.cached and self.cached_for == location and time.time() - self.fetched < KEEP:
            return self.cached
        try:
            async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as http:
                async with http.get(SOLAR_URL) as r:
                    r.raise_for_status()
                    report = parse_solar(await r.read())
                report["sonde"] = None
                if location:
                    try:   # the figures are worth showing without the MUF
                        async with http.get(SONDES_URL) as r:
                            r.raise_for_status()
                            report["sonde"] = nearest_sonde(await r.json(content_type=None), tuple(location))
                    except (aiohttp.ClientError, TimeoutError, ValueError):
                        pass
        except (aiohttp.ClientError, TimeoutError, ET.ParseError, AttributeError):
            if self.cached:
                return self.cached
            raise RuntimeError("propagation data unreachable")
        self.cached, self.cached_for, self.fetched = report, location, time.time()
        return report
