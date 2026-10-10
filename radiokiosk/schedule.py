"""Who is on the air on shortwave right now, from the EiBi schedule.

EiBi (Eike Bierwirth, eibispace.de) publishes a free list of broadcast
schedules twice a year. It is fetched once and kept in the cache folder.
"""

import asyncio
import re
import time

import aiohttp

from .config import CACHE_DIR

URL = "http://www.eibispace.de/dx/sked-{season}.csv"   # the site does not offer https
KEEP = 14 * 86400
DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
# the shortwave broadcast bands in kHz, a little wider than assigned: many stations sit just outside
BROADCAST = ((2300, 2495), (3200, 3400), (3900, 4000), (4750, 5060), (5800, 6450), (7200, 7800), (9250, 9900),
             (11500, 12160), (13570, 13870), (15030, 15800), (17480, 17900), (18900, 19020), (21450, 21850),
             (25600, 26100))
EUROPE = {"Eu", "WEu", "CEu", "NEu", "SEu", "EEu"}
ONE_OFF = re.compile(r"\d[A-Z][a-z]{2}|Test")   # a date such as 31May: a single broadcast
NOT_SPEECH = ("DIGITAL", "RTTY", "Fax")


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


def _joined(times):
    """Hours that overlap or follow each other on the same days, as one stretch each."""
    joined = []
    for start, stop, days in sorted(times, key=lambda t: (t[2], t[0], t[1])):
        last = joined[-1] if joined else None
        if last and last[2] == days and last[0] < last[1] and start <= last[1]:
            if start < stop:
                last[1] = max(last[1], stop)
            elif stop < last[0]:
                last[1] = stop       # runs on past midnight
            else:
                last[0], last[1] = 0, 2400
        else:
            joined.append([start, stop, days])
    return joined


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

    def broadcasts(self, now=None):
        """Shortwave broadcasters worth a try from Europe, in three groups: in German, in English to Europe,
        in other languages to Europe. One row per station and frequency with all its hours; those
        transmitting at this moment come first."""
        t = time.gmtime(now)
        clock, weekday = t.tm_hour * 100 + t.tm_min, t.tm_wday
        groups = {"german": {}, "english": {}, "others": {}}
        for khz, start, stop, days, station, language, target in self.entries:
            if not language or ONE_OFF.search(days) or any(word in station for word in NOT_SPEECH) \
                    or not any(low <= khz <= high for low, high in BROADCAST):
                continue   # no language: fax and data; DRM is only noise to an AM receiver
            spoken = language.split(",")
            if "D" in spoken:
                group = "german"
            elif target in EUROPE:
                group = "english" if "E" in spoken else "others"
            else:
                continue
            row = groups[group].setdefault((station, khz), {"khz": khz, "station": station, "language": language,
                                                              "times": [], "now": False})
            row["times"].append([start, stop, days])
            running = start <= clock < stop if start < stop else clock >= start or clock < stop
            row["now"] = row["now"] or (running and _on_day(days, weekday))
        for rows in groups.values():
            for row in rows.values():
                row["times"] = _joined(row["times"])
        return {name: sorted(rows.values(), key=lambda r: (not r["now"], r["station"].lower(), r["khz"]))
                for name, rows in groups.items()}

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
