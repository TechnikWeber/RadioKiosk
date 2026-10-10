"""Official weather warnings for the own location, from the German weather service (DWD).

Read through Bright Sky (brightsky.dev), which serves the DWD's open data
without a key. Only places in Germany have warnings.
"""

import asyncio
import calendar
import time

import aiohttp

from .feeds import HEADERS

URL = "https://api.brightsky.dev/alerts"
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


class Alerts:
    def __init__(self, core):
        self.core = core
        core.state["alerts"] = []

    async def look(self):
        location = self.core.cfg.get("location")
        if not self.core.cfg["alerts"] or not location:
            self.core.update(alerts=[])
            return
        try:
            async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as http:
                async with http.get(URL, params={"lat": str(location[0]), "lon": str(location[1])}) as r:
                    if r.status == 404:   # a place outside Germany
                        self.core.update(alerts=[])
                        return
                    r.raise_for_status()
                    self.core.update(alerts=parse(await r.json(content_type=None)))
        except (aiohttp.ClientError, TimeoutError, ValueError):
            pass   # no connection: what was last known stays until it expires in the interface

    async def run(self):
        while True:
            await self.look()
            await asyncio.sleep(EVERY)
