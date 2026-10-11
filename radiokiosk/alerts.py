"""Official warnings for the own location: the weather from the German weather service (DWD),
and what civil protection sends out through NINA (floods, fires, drinking water, bomb disposal).

The weather is read through Bright Sky (brightsky.dev), which serves the DWD's open data
without a key; the others from the federal warning portal (warnung.bund.de), which lists all
warnings in force with the area each one is for. Only places in Germany have warnings.
"""

import asyncio
import calendar
import time

import aiohttp

from . import tones
from .feeds import HEADERS, plain

URL = "https://api.brightsky.dev/alerts"
NINA = "https://warnung.bund.de/api31"
# who sends them: the federal system, two systems of towns and districts, the flood centres, the police.
# The weather service's own are left out here, they come above with more detail.
NINA_SOURCES = ("mowas", "katwarn", "biwapp", "lhp", "police")
EVERY = 10 * 60   # seconds between looks


def _moment(text):
    try:
        base = calendar.timegm(time.strptime(text[:19], "%Y-%m-%dT%H:%M:%S"))
        sign, offset = text[19:20], text[20:25]
        if sign in "+-" and len(offset) == 5:   # +02:00
            base -= (1 if sign == "+" else -1) * (int(offset[:2]) * 3600 + int(offset[3:]) * 60)
        return base
    except (ValueError, TypeError):
        return 0


def parse(data, now=None):
    """The warnings in force, the most severe first."""
    now = now or time.time()
    order = {"extreme": 0, "severe": 1, "moderate": 2, "minor": 3}
    found = []
    for a in data.get("alerts", []):
        until = _moment(a.get("expires") or "")
        if until and until < now:
            continue
        found.append({"severity": a.get("severity") or "minor", "from": _moment(a.get("onset") or a.get("effective") or ""),
                      "until": until,
                      **{f"{field}_{lang}": (a.get(f"{field}_{lang}") or "").strip()
                         for field in ("event", "headline", "description", "instruction") for lang in ("de", "en")}})
    return sorted(found, key=lambda a: (order.get(a["severity"], 4), a["from"]))


def inside(point, ring):
    """Whether a point (lon, lat) lies within a closed line of such points."""
    x, y = point
    within = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            within = not within
    return within


def covers(area, point):
    """Whether the area of a warning (GeoJSON) includes the point; holes in an area count as outside."""
    for feature in area.get("features", []):
        geometry = feature.get("geometry") or {}
        shapes = {"Polygon": [geometry.get("coordinates")], "MultiPolygon": geometry.get("coordinates")}.get(geometry.get("type")) or []
        for shape in shapes:
            if shape and inside(point, [p[:2] for p in shape[0]]) and not any(inside(point, [p[:2] for p in hole]) for hole in shape[1:]):
                return True
    return False


def from_nina(detail, listed, now=None):
    """A warning of the portal in the shape the weather warnings have; None once it is over or called off."""
    info = next((i for i in detail.get("info", []) if i.get("language", "").lower().startswith("de")), None) or (detail.get("info") or [{}])[0]
    until = _moment(info.get("expires") or "")
    if (until and until < (now or time.time())) or detail.get("msgType") == "Cancel":
        return None
    severity = (info.get("severity") or listed.get("severity") or "minor").lower()
    return {"severity": severity if severity in ("extreme", "severe", "moderate", "minor") else "minor",
            "from": _moment(info.get("onset") or info.get("effective") or detail.get("sent") or ""), "until": until,
            "event_de": plain(info.get("event") or ""), "headline_de": plain(info.get("headline") or ""),
            "description_de": plain(info.get("description") or "", 1500), "instruction_de": plain(info.get("instruction") or "", 800),
            "event_en": "", "headline_en": "", "description_en": "", "instruction_en": ""}


class Alerts:
    def __init__(self, core):
        self.core = core
        core.state["alerts"] = []
        self.weather = []
        self.others = []
        self.checked = {}   # (id, version) of a portal warning -> its alert here, or None if it is for elsewhere
        self.extreme = None   # the warnings of the highest level seen so far; None before the first look

    async def look_nina(self, http, location):
        """What the warning portal has for this place. An area is looked at once per version of a warning."""
        point, current, found = (location[1], location[0]), {}, []
        for source in NINA_SOURCES:
            try:
                async with http.get(f"{NINA}/{source}/mapData.json") as r:
                    r.raise_for_status()
                    listed = await r.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError, ValueError):
                return   # no answer: what was last known stays
            for warning in listed if isinstance(listed, list) else []:
                key = (warning.get("id"), warning.get("version"))
                if key not in self.checked:
                    try:
                        async with http.get(f"{NINA}/warnings/{key[0]}.geojson") as r:
                            r.raise_for_status()
                            here = covers(await r.json(content_type=None), point)
                        detail = None
                        if here:
                            async with http.get(f"{NINA}/warnings/{key[0]}.json") as r:
                                r.raise_for_status()
                                detail = (await r.json(content_type=None), warning)
                    except (aiohttp.ClientError, TimeoutError, ValueError, TypeError, IndexError, ZeroDivisionError):
                        continue   # looked at again next time
                    self.checked[key] = detail
                current[key] = self.checked[key]
        self.checked = current   # warnings no longer listed are forgotten
        for detail in current.values():
            alert = detail and from_nina(*detail)
            if alert:
                found.append(alert)
        self.others = found

    def tell(self):
        order = {"extreme": 0, "severe": 1, "moderate": 2, "minor": 3}
        found = sorted(self.weather + self.others, key=lambda a: (order.get(a["severity"], 4), a["from"]))
        self.core.update(alerts=found)
        # A sound for a new warning of the highest level, where that is switched on. Not for what is
        # found at the first look: the service restarts with every update and would sound each time.
        extreme = {(a["headline_de"], a["from"], a["until"]) for a in found if a["severity"] == "extreme"}
        if self.extreme is not None and extreme - self.extreme and self.core.cfg["alert_tone"]:
            asyncio.create_task(tones.play(self.core.cfg["tone"], 4))
        self.extreme = extreme

    async def look(self):
        location = self.core.cfg.get("location")
        if not self.core.cfg["alerts"] or not location:
            self.weather, self.others = [], []
            self.core.update(alerts=[])
            return
        try:
            async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=20)) as http:
                async with http.get(URL, params={"lat": str(location[0]), "lon": str(location[1])}) as r:
                    if r.status == 404:   # a place outside Germany
                        self.weather, self.others = [], []
                        self.core.update(alerts=[])
                        return
                    r.raise_for_status()
                    self.weather = parse(await r.json(content_type=None))
                await self.look_nina(http, location)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            pass   # no connection: what was last known stays until it expires in the interface
        self.tell()

    async def run(self):
        while True:
            await self.look()
            await asyncio.sleep(EVERY)
