"""Calendars read from their iCal address, as one list of what comes next.

Nearly everything with dates offers such an address: a private Google or Apple
calendar, the waste collection dates of a town, school holidays, a club's
fixtures. Each calendar is fetched now and then and kept, so the dates are also
there without a connection. Nothing is written back.

The reading understands what such calendars use: all-day and timed events,
time zones, repeats by day, week, month and year with their exceptions. It
needs nothing beyond the standard library.
"""

import asyncio
import datetime
import re
import time
import uuid
from zoneinfo import ZoneInfo

import aiohttp

from .config import CACHE_DIR, load_json, save_json
from .feeds import HEADERS

KEPT = CACHE_DIR / "calendars"
FETCH_EVERY = 30 * 60
LOOK_EVERY = 5 * 60
AHEAD = 90            # days the list looks ahead
MOST = 300            # events in the list
MAX_SIZE = 8 * 1024 * 1024
MAX_CALENDARS = 12
MAX_REPEATS = 4000    # steps a repeating event is followed before giving up
DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
DAY = datetime.timedelta(days=1)


def unfold(text):
    """The lines of a calendar file; a line that starts with a blank continues the one before."""
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        elif line:
            lines.append(line)
    return lines


def plain(value):
    return re.sub(r"\\([,;\\])", r"\1", value.replace("\\n", " ").replace("\\N", " ")).strip()


def moment(value, params):
    """A date or time of the file as (local time without zone, all_day)."""
    value = value.strip()
    if len(value) == 8:
        return datetime.datetime.strptime(value, "%Y%m%d"), True
    stamp = datetime.datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    zone = datetime.timezone.utc if value.endswith("Z") else None
    if zone is None and params.get("TZID"):
        try:
            zone = ZoneInfo(params["TZID"])
        except (KeyError, ValueError):
            zone = None   # an unknown zone: taken as the time on the wall here
    if zone is not None:
        stamp = stamp.replace(tzinfo=zone).astimezone().replace(tzinfo=None)
    return stamp, False


def events_of(text):
    """Every VEVENT of a calendar file as a dict of its properties: name -> list of (params, value)."""
    found, current = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            if current is not None:
                found.append(current)
            current = None
        elif current is not None and ":" in line:
            head, value = line.split(":", 1)
            name, *rest = head.split(";")
            params = dict(p.split("=", 1) for p in rest if "=" in p)
            current.setdefault(name.upper(), []).append((params, value))
    return found


def month_days(year, month):
    following = datetime.date(year + month // 12, month % 12 + 1, 1)
    return (following - datetime.date(year, month, 1)).days


def repeats(start, rule, until):
    """The moments a repeating event takes place, from its first one up to `until`."""
    parts = dict(p.split("=", 1) for p in rule.split(";") if "=" in p)
    freq, every = parts.get("FREQ", ""), max(1, int(parts.get("INTERVAL", "1")))
    count = int(parts["COUNT"]) if parts.get("COUNT", "").isdigit() else None
    if parts.get("UNTIL"):
        try:
            last, all_day = moment(parts["UNTIL"], {})
            until = min(until, last + DAY if all_day else last)
        except ValueError:
            pass
    by_day = [d for d in parts.get("BYDAY", "").split(",") if d]
    by_month_day = [int(d) for d in parts.get("BYMONTHDAY", "").split(",") if d.lstrip("-").isdigit()]
    given = 0

    def candidates(step):
        if freq == "DAILY":
            return [start + DAY * (step * every)]
        if freq == "WEEKLY":
            monday = start - DAY * start.weekday() + DAY * (7 * step * every)
            wanted = [DAYS.index(d[-2:]) for d in by_day if d[-2:] in DAYS] or [start.weekday()]
            return [monday + DAY * day for day in sorted(wanted)]
        if freq in ("MONTHLY", "YEARLY"):
            months = start.month - 1 + step * every * (1 if freq == "MONTHLY" else 12)
            year, month = start.year + months // 12, months % 12 + 1
            length = month_days(year, month)
            numbers = []
            if by_month_day:
                numbers = [d if d > 0 else length + 1 + d for d in by_month_day]
            elif by_day and freq == "MONTHLY":
                for item in by_day:   # 2TU the second Tuesday, -1FR the last Friday, TU every Tuesday
                    if item[-2:] not in DAYS:
                        continue
                    matching = [d for d in range(1, length + 1)
                                if datetime.date(year, month, d).weekday() == DAYS.index(item[-2:])]
                    nth = item[:-2]
                    if nth.lstrip("+-").isdigit():
                        index = int(nth)
                        if 0 < index <= len(matching) or 0 < -index <= len(matching):
                            numbers.append(matching[index - 1 if index > 0 else index])
                    else:
                        numbers += matching
            else:
                numbers = [start.day]
            return [start.replace(year=year, month=month, day=d) for d in sorted(set(numbers)) if 1 <= d <= length]
        return []

    if freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        yield start
        return
    for step in range(MAX_REPEATS):
        for when in candidates(step):
            if when < start:
                continue
            if when > until or (count is not None and given >= count):
                return
            given += 1
            yield when


def upcoming(text, since, until):
    """What a calendar file holds between two moments, as a list of events sorted by their start."""
    raw = events_of(text)
    first = lambda event, name: event.get(name, [({}, "")])[0]
    moved = {}   # (uid, original moment) of single dates that were changed within a repeating event
    for event in raw:
        if "RECURRENCE-ID" in event:
            try:
                moved[(first(event, "UID")[1], moment(first(event, "RECURRENCE-ID")[1], first(event, "RECURRENCE-ID")[0])[0])] = True
            except ValueError:
                pass
    found = []
    for event in raw:
        if first(event, "STATUS")[1].upper() == "CANCELLED" or "DTSTART" not in event:
            continue
        try:
            start, all_day = moment(first(event, "DTSTART")[1], first(event, "DTSTART")[0])
            if "DTEND" in event:
                length = moment(first(event, "DTEND")[1], first(event, "DTEND")[0])[0] - start
            else:
                length = DAY if all_day else datetime.timedelta()
            left_out = set()
            for params, value in event.get("EXDATE", []):
                left_out.update(moment(v, params)[0] for v in value.split(",") if v.strip())
        except ValueError:
            continue
        uid = first(event, "UID")[1]
        rule = first(event, "RRULE")[1]
        single = "RECURRENCE-ID" in event or not rule
        for when in ([start] if single else repeats(start, rule, until)):
            if when in left_out or (not single and (uid, when) in moved):
                continue
            if when + max(length, datetime.timedelta(minutes=1)) <= since or when > until:
                continue
            found.append({"start": when.isoformat(timespec="minutes"), "end": (when + length).isoformat(timespec="minutes"),
                          "all_day": all_day, "title": plain(first(event, "SUMMARY")[1]) or "–",
                          "place": plain(first(event, "LOCATION")[1])})
    return sorted(found, key=lambda e: (e["start"], not e["all_day"], e["title"]))


class Agenda:
    def __init__(self, core):
        self.core = core
        self.calendars = load_json("calendars.json", [])   # {"id", "name", "url"}
        self.problems = {}    # calendar id -> what went wrong at the last fetch
        self.fetched = {}     # calendar id -> time of the last successful fetch
        core.state["agenda"] = []

    def file(self, calendar):
        return KEPT / f"{calendar['id']}.ics"

    async def fetch(self, calendar):
        try:
            async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as http:
                async with http.get(calendar["url"]) as reply:
                    reply.raise_for_status()
                    data = await reply.content.read(MAX_SIZE)
            text = data.decode("utf-8", errors="replace")
            if "BEGIN:VCALENDAR" not in text:
                raise ValueError
        except (aiohttp.ClientError, TimeoutError, OSError):
            self.problems[calendar["id"]] = "the calendar cannot be reached"
            return False
        except ValueError:
            self.problems[calendar["id"]] = "this address does not lead to a calendar"
            return False
        KEPT.mkdir(parents=True, exist_ok=True)
        partial = self.file(calendar).with_suffix(".part")
        partial.write_text(text, encoding="utf-8")
        partial.replace(self.file(calendar))
        self.problems.pop(calendar["id"], None)
        self.fetched[calendar["id"]] = time.time()
        return True

    def events(self, days=AHEAD, now=None):
        """What all calendars hold from today on, each event with the name of its calendar."""
        now = now or datetime.datetime.now()
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        found = []
        for calendar in self.calendars:
            try:
                text = self.file(calendar).read_text(encoding="utf-8")
            except OSError:
                continue
            found += [{**e, "calendar": calendar["name"]} for e in upcoming(text, since, since + DAY * days)]
        # what is over is left out, but an all-day event stays for its day
        found = [e for e in found if e["end"] > now.isoformat(timespec="minutes") or (e["all_day"] and e["end"] > since.isoformat())]
        return sorted(found, key=lambda e: (e["start"], not e["all_day"], e["title"]))[:MOST]

    def soon(self, now=None):
        """For the idle screen: what is on today and tomorrow."""
        now = now or datetime.datetime.now()
        limit = (now.replace(hour=0, minute=0, second=0, microsecond=0) + DAY * 2).isoformat()
        return [{k: e[k] for k in ("start", "all_day", "title")} for e in self.events(2, now) if e["start"] < limit][:6]

    def tell(self):
        self.core.update(agenda=self.soon())

    def listing(self):
        return {"events": self.events(), "calendars": [{**c, "problem": self.problems.get(c["id"])} for c in self.calendars]}

    async def add(self, name, url):
        url = url.strip()
        if url.lower().startswith("webcal://"):   # how calendar programs write an address to subscribe to
            url = "https://" + url[9:]
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("this is not an address")
        if len(self.calendars) >= MAX_CALENDARS:
            raise ValueError("there are too many calendars already")
        calendar = {"id": uuid.uuid4().hex[:12], "name": name.strip()[:40] or "Kalender", "url": url}
        if not await self.fetch(calendar):
            raise RuntimeError(self.problems.pop(calendar["id"]))
        self.calendars.append(calendar)
        save_json("calendars.json", self.calendars)
        self.tell()

    def remove(self, calendar_id):
        for calendar in self.calendars:
            if calendar["id"] == calendar_id:
                self.file(calendar).unlink(missing_ok=True)
        self.calendars = [c for c in self.calendars if c["id"] != calendar_id]
        save_json("calendars.json", self.calendars)
        self.tell()

    async def refresh(self):
        for calendar in list(self.calendars):
            await self.fetch(calendar)
        self.tell()

    async def run(self):
        while True:
            for calendar in list(self.calendars):
                if time.time() - self.fetched.get(calendar["id"], 0) > FETCH_EVERY:
                    await self.fetch(calendar)
            self.tell()   # also without a fetch: what was "tomorrow" becomes "today"
            await asyncio.sleep(LOOK_EVERY)
