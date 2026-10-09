"""Who is on the air on shortwave right now, from the EiBi schedule.

EiBi (Eike Bierwirth, eibispace.de) publishes a free list of broadcast
schedules twice a year. It is fetched once and kept in the cache folder.
"""

import asyncio
import time

import aiohttp

from .config import CACHE_DIR

URL = "http://www.eibispace.de/dx/sked-{season}.csv"   # the site does not offer https
KEEP = 14 * 86400
DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def seasons(now=None):
    """The current season code first, then the previous one as a fallback (a26, b25, ...)."""
    t = time.gmtime(now)
    year, yday = t.tm_year % 100, t.tm_yday
    # summer schedules (A) run from the end of March to the end of October
    if 88 <= yday < 300:
        return [f"a{year:02d}", f"b{year - 1:02d}"]
    if yday >= 300:
        return [f"b{year:02d}", f"a{year:02d}"]
    return [f"b{year - 1:02d}", f"a{year - 1:02d}"]


def _on_day(days, weekday):
    """EiBi's day field: empty for daily, 'Mo-Fr', 'Sa,Su' or digits with 1 = Monday."""
    if not days:
        return True
    if days.isdigit():
        return str(weekday + 1) in days
    for part in days.split(","):
        if "-" in part:
            first, _, last = part.partition("-")
            if first in DAYS and last in DAYS:
                a, b = DAYS.index(first), DAYS.index(last)
                if (a <= weekday <= b) if a <= b else (weekday >= a or weekday <= b):
                    return True
        elif part == DAYS[weekday]:
            return True
    return not any(d in days for d in DAYS)   # codes like "irr": do not hide the station


class Schedule:
    def __init__(self):
        self.entries = []     # (kHz, start, stop, days, station, language, target)
        self.loading = None

    async def _load(self):
        path = CACHE_DIR / "eibi.csv"
        if not path.exists() or time.time() - path.stat().st_mtime > KEEP:
            for season in seasons():
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as http:
                        async with http.get(URL.format(season=season)) as r:
                            if r.status == 200:
                                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                                path.write_bytes(await r.read())
                                break
                except (aiohttp.ClientError, TimeoutError):
                    continue
        if path.exists():
            self.entries = self.parse(path.read_text(encoding="latin-1"))

    @staticmethod
    def parse(text):
        entries = []
        for line in text.splitlines()[1:]:
            f = line.split(";")
            try:
                khz, (start, stop) = float(f[0]), f[1].split("-")
                # language codes starting with "-" mark utility stations (time signals, navies, ...)
                if khz >= 150 and not f[5].startswith("-"):
                    entries.append((khz, int(start), int(stop), f[2], f[4], f[5], f[6]))
            except (ValueError, IndexError):
                continue
        return entries

    async def ready(self):
        if not self.entries:
            self.loading = self.loading or asyncio.create_task(self._load())
            await self.loading
            self.loading = None
        return bool(self.entries)

    def on_air(self, low_khz, high_khz, now=None):
        """Stations transmitting between the two frequencies at this moment."""
        t = time.gmtime(now)
        clock, weekday = t.tm_hour * 100 + t.tm_min, t.tm_wday
        found = {}
        for khz, start, stop, days, station, language, target in self.entries:
            if not low_khz <= khz <= high_khz:
                continue
            running = start <= clock < stop if start < stop else clock >= start or clock < stop
            if running and _on_day(days, weekday):
                found.setdefault((khz, station), {"khz": khz, "station": station, "language": language,
                                                  "target": target})
        return sorted(found.values(), key=lambda e: e["khz"])
