"""Short notes, and reminders for a day that stay up until somebody acknowledges them.

Both are plain lists in the configuration folder. Nothing here knows about
radio; the module stands on its own.
"""

import asyncio
import calendar
import datetime
import time
import uuid

from .config import load_json, save_json
from .qsolog import documents_dir
from . import tones

NOTE_LENGTH = 2000
REMINDER_LENGTH = 300
REPEATS = ("", "day", "week", "month", "year")
SNOOZES = (10, 60, 1440)          # minutes a reminder can be put off
KEEP_DONE = 30 * 86400            # an acknowledged reminder stays in the list this long
LOOK_EVERY = 20
MORNING = 7                       # hour at which a reminder without a time of day comes up
TONE_FOR = 4   # seconds; the tone lies over what is playing, like the timer's


class Notes:
    def __init__(self):
        self.items = load_json("notes.json", [])

    def list(self):
        """Pinned notes first, then the most recently changed."""
        return sorted(self.items, key=lambda n: (not n.get("pinned"), -n.get("changed", 0)))

    def save(self, entry):
        text = str(entry.get("text", "")).strip()[:NOTE_LENGTH]
        if not text:
            raise ValueError("a note needs some text")
        note = next((n for n in self.items if n["id"] == entry.get("id")), None)
        if note is None:
            note = {"id": uuid.uuid4().hex[:12], "pinned": False}
            self.items.append(note)
        if note.get("text") != text:
            note["changed"] = time.time()
        note["text"] = text
        if isinstance(entry.get("pinned"), bool):
            note["pinned"] = entry["pinned"]
        save_json("notes.json", self.items)
        return note

    def delete(self, note_id):
        self.items = [n for n in self.items if n["id"] != note_id]
        save_json("notes.json", self.items)

    def export(self):
        """All notes as one text file in the documents folder; returns its path."""
        folder = documents_dir()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / time.strftime("notes_%Y-%m-%d_%H%M.txt")
        stamp = lambda n: time.strftime("%Y-%m-%d %H:%M", time.localtime(n.get("changed", 0)))
        path.write_text("\n\n".join(f"{stamp(n)}\n{n['text']}" for n in self.list()) + "\n", encoding="utf-8")
        return path


def step(day, repeat):
    """The day a repeating reminder comes up next after `day`."""
    if repeat == "day":
        return day + datetime.timedelta(days=1)
    if repeat == "week":
        return day + datetime.timedelta(days=7)
    year, month = (day.year, day.month + 1) if repeat == "month" else (day.year + 1, day.month)
    if month > 12:
        year, month = year + 1, 1
    # the 31st in a month of thirty days, or 29 February in a common year: the month's last day
    return datetime.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def moment(reminder):
    """When a reminder comes up, as local time: at its time of day, or in the morning of its day.
    Midnight would be the start of the day, but nobody wants a tone and a bright display then."""
    day = datetime.date.fromisoformat(reminder["date"])
    hour, minute = (int(part) for part in reminder["time"].split(":")) if reminder.get("time") else (MORNING, 0)
    return datetime.datetime(day.year, day.month, day.day, hour, minute)


class Reminders:
    def __init__(self, core):
        self.core = core
        self.items = load_json("reminders.json", [])
        core.state["reminders"] = []

    def clean(self, entry):
        """A reminder as the list keeps it; raises ValueError where text, day or time make no sense."""
        text = str(entry.get("text", "")).strip()[:REMINDER_LENGTH]
        if not text:
            raise ValueError("a reminder needs some text")
        try:
            day = datetime.date.fromisoformat(str(entry.get("date", "")))
        except ValueError:
            raise ValueError("this is not a date")
        clock = str(entry.get("time") or "")
        if clock:
            try:
                clock = datetime.time.fromisoformat(clock).strftime("%H:%M")
            except ValueError:
                raise ValueError("this is not a time of day")
        repeat = entry.get("repeat") if entry.get("repeat") in REPEATS else ""
        return {"text": text, "date": day.isoformat(), "time": clock, "repeat": repeat}

    def list(self, now=None):
        """What is due first, then what is still to come by date, then what was acknowledged."""
        now = now or datetime.datetime.now()
        rank = lambda r: (2, -moment(r).timestamp()) if r.get("done") else (0 if moment(r) <= now else 1, moment(r).timestamp())
        return [{**r, "due": self.is_due(r, now)} for r in sorted(self.items, key=rank)]

    def is_due(self, reminder, now):
        return not reminder.get("done") and moment(reminder) <= now and reminder.get("snoozed", 0) <= now.timestamp()

    def due(self, now=None):
        now = now or datetime.datetime.now()
        return [{"id": r["id"], "text": r["text"], "date": r["date"], "time": r["time"]}
                for r in sorted(self.items, key=lambda r: moment(r)) if self.is_due(r, now)]

    def store(self):
        save_json("reminders.json", self.items)
        self.core.update(reminders=self.due())

    def save(self, entry):
        record = self.clean(entry)
        reminder = next((r for r in self.items if r["id"] == entry.get("id")), None)
        if reminder is None:
            reminder = {"id": uuid.uuid4().hex[:12]}
            self.items.append(reminder)
        # a changed reminder starts afresh: it may have been acknowledged or put off for its old day
        reminder.update(record, done=False, snoozed=0)
        self.store()
        return reminder

    def delete(self, reminder_id):
        self.items = [r for r in self.items if r["id"] != reminder_id]
        self.store()

    def acknowledge(self, reminder_id, now=None):
        """Seen and dealt with. A repeating reminder moves on to its next day instead of ending."""
        now = now or datetime.datetime.now()
        for reminder in self.items:
            if reminder["id"] != reminder_id:
                continue
            reminder["snoozed"] = 0
            if reminder["repeat"]:
                day = datetime.date.fromisoformat(reminder["date"])
                while True:   # one that was missed for weeks does not come up once for every week
                    day = step(day, reminder["repeat"])
                    reminder["date"] = day.isoformat()
                    if moment(reminder) > now:
                        break
            else:
                reminder.update(done=True, done_at=now.timestamp())
        self.store()

    def snooze(self, reminder_id, minutes, now=None):
        if minutes not in SNOOZES:
            raise ValueError("unknown setting")
        for reminder in self.items:
            if reminder["id"] == reminder_id:
                reminder["snoozed"] = (now or time.time()) + minutes * 60
        self.store()

    async def run(self):
        """Tell the interfaces when a reminder comes up, and drop acknowledged ones after a month."""
        while True:
            fresh = [r for r in self.items if not r.get("done") or time.time() - r.get("done_at", 0) < KEEP_DONE]
            if len(fresh) != len(self.items):
                self.items = fresh
                save_json("reminders.json", self.items)
            due = self.due()
            shown = self.core.state.get("reminders") or []
            if due != shown:
                self.core.update(reminders=due)
                if {r["id"] for r in due} - {r["id"] for r in shown}:
                    await tones.play(self.core.cfg["tone"], TONE_FOR)
            await asyncio.sleep(LOOK_EVERY)
