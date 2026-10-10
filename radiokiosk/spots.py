"""Who is on the air right now: spots from the DX cluster and from Parks on the Air.

A spot is one operator telling the others "this station is on this frequency
now". Both sources are free and need no key:
- the DX cluster through HamQTH (Petr, OK2CQR), with DX Summit (OH8X) to fall back on,
- Parks on the Air through the programme's own interface.
"""

import calendar
import time

import aiohttp

from .feeds import HEADERS
from .qsolog import band_of

KEEP = 60        # seconds spots stay fresh; the sources ask not to be polled faster
DX_URL = "https://www.hamqth.com/dxc_csv.php"
DX_FALLBACK = "https://www.dxsummit.fi/api/v1/spots"
POTA_URL = "https://api.pota.app/spot/activator"
MODES = ("FT8", "FT4", "CW", "SSB", "RTTY", "FM", "PSK", "SSTV", "AM", "JS8")


def _moment(text, pattern):
    try:
        return calendar.timegm(time.strptime(text.strip()[:19], pattern))
    except ValueError:
        return 0


def mode_in(text):
    """The mode a spot's comment mentions, if any."""
    words = text.upper().replace(",", " ").split()
    return next((mode for mode in MODES if mode in words), "")


def _spot(dx, khz, spotter, comment, moment, where="", mode=""):
    return {"dx": dx.strip().upper(), "khz": round(khz, 1), "band": band_of(khz / 1000), "spotter": spotter.strip(),
            "comment": comment.strip(), "time": moment, "where": where.strip(), "mode": mode or mode_in(comment)}


def parse_hamqth(text):
    """HamQTH's list: spotter^kHz^dx^comment^HHMM YYYY-MM-DD^...^continent^band^country^..., one spot per line."""
    spots = []
    for line in text.splitlines():
        f = line.split("^")
        try:
            spots.append(_spot(f[2], float(f[1]), f[0], f[3], _moment(f[4], "%H%M %Y-%m-%d"), f[9] if len(f) > 9 else ""))
        except (IndexError, ValueError):
            continue
    return spots


def parse_dxsummit(rows):
    spots = []
    for r in rows:
        try:
            spots.append(_spot(r["dx_call"], float(r["frequency"]), r.get("de_call") or "", r.get("info") or "",
                               _moment(r.get("time") or "", "%Y-%m-%dT%H:%M:%S"), r.get("dx_country") or ""))
        except (KeyError, TypeError, ValueError):
            continue
    return spots


def parse_pota(rows):
    spots = []
    for r in rows:
        try:
            park = " ".join(filter(None, [r.get("reference"), r.get("name")]))
            spots.append({**_spot(r["activator"], float(r["frequency"]), r.get("spotter") or "", r.get("comments") or "",
                                  _moment(r.get("spotTime") or "", "%Y-%m-%dT%H:%M:%S"),
                                  ", ".join(filter(None, [park, r.get("locationDesc")])), (r.get("mode") or "").upper())})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(spots, key=lambda s: -s["time"])


class Spots:
    def __init__(self):
        self.cached = {}   # kind -> (time, source, spots)

    async def _fetch(self, url, params=None, as_json=False):
        async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as http:
            async with http.get(url, params=params) as r:
                r.raise_for_status()
                return await r.json(content_type=None) if as_json else await r.text()

    async def _read(self, kind):
        if kind == "pota":
            return "Parks on the Air", parse_pota(await self._fetch(POTA_URL, as_json=True))
        try:
            spots = parse_hamqth(await self._fetch(DX_URL, {"limit": "60"}))
            if spots:
                return "HamQTH", spots
        except (aiohttp.ClientError, TimeoutError, ValueError):
            pass
        return "DX Summit", parse_dxsummit(await self._fetch(DX_FALLBACK, {"limit": "60"}, as_json=True))

    async def get(self, kind):
        """The newest spots of a kind ("dx" or "pota"), newest first."""
        kind = "pota" if kind == "pota" else "dx"
        cached = self.cached.get(kind)
        if cached and time.time() - cached[0] < KEEP:
            return {"source": cached[1], "spots": cached[2], "age": 0}
        try:
            source, spots = await self._read(kind)
        except (aiohttp.ClientError, TimeoutError, ValueError, TypeError):
            if cached:   # better a few minutes old than nothing
                return {"source": cached[1], "spots": cached[2], "age": round(time.time() - cached[0])}
            raise RuntimeError("the spots cannot be reached")
        self.cached[kind] = (time.time(), source, spots)
        return {"source": source, "spots": spots, "age": 0}
