import datetime
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from radiokiosk import config, notes
from radiokiosk.notes import Notes, Reminders, step


class FakeCore:
    def __init__(self):
        self.state = {}

    def update(self, **changes):
        self.state.update(changes)


class InOwnFolder(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        patch = mock.patch.object(config, "CONFIG_DIR", Path(folder.name))
        patch.start()
        self.addCleanup(patch.stop)


class NotesTest(InOwnFolder):
    def test_pinned_first_then_newest(self):
        book = Notes()
        first, second = book.save({"text": "milk"}), book.save({"text": "call Anna"})
        book.save({"id": first["id"], "text": "milk", "pinned": True})
        self.assertEqual([n["text"] for n in book.list()], ["milk", "call Anna"])
        self.assertEqual([n["text"] for n in Notes().list()], ["milk", "call Anna"])   # read back from the file
        book.delete(first["id"])
        self.assertEqual([n["id"] for n in book.list()], [second["id"]])

    def test_an_empty_note_is_refused(self):
        with self.assertRaises(ValueError):
            Notes().save({"text": "   "})


class RemindersTest(InOwnFolder):
    def setUp(self):
        super().setUp()
        self.core = FakeCore()
        self.list = Reminders(self.core)

    def test_due_from_its_day_or_time_until_acknowledged(self):
        r = self.list.save({"text": "bins out", "date": "2026-10-12", "time": "18:30"})
        at = lambda *moment: datetime.datetime(2026, 10, *moment)
        self.assertEqual(self.list.due(at(12, 18, 29)), [])
        self.assertEqual([d["text"] for d in self.list.due(at(12, 18, 30))], ["bins out"])
        self.assertEqual([d["text"] for d in self.list.due(at(14, 9, 0))], ["bins out"])   # still there two days on
        self.list.acknowledge(r["id"], at(14, 9, 0))
        self.assertEqual(self.list.due(at(14, 9, 1)), [])
        self.assertTrue(self.list.items[0]["done"])

    def test_without_a_time_it_is_due_in_the_morning(self):
        self.list.save({"text": "birthday", "date": "2026-10-12"})
        self.assertEqual(self.list.due(datetime.datetime(2026, 10, 12, 6, 59)), [])
        self.assertEqual(len(self.list.due(datetime.datetime(2026, 10, 12, 7, 0))), 1)

    def test_a_repeating_one_moves_on_past_today(self):
        r = self.list.save({"text": "water plants", "date": "2026-10-01", "repeat": "week"})
        self.list.acknowledge(r["id"], datetime.datetime(2026, 10, 20, 8, 0))   # missed for almost three weeks
        self.assertEqual(self.list.items[0]["date"], "2026-10-22")
        self.assertFalse(self.list.items[0].get("done"))

    def test_put_off(self):
        r = self.list.save({"text": "call back", "date": "2026-10-12", "time": "10:00"})
        now = datetime.datetime(2026, 10, 12, 10, 5)
        self.list.snooze(r["id"], 60, now.timestamp())
        self.assertEqual(self.list.due(now + datetime.timedelta(minutes=59)), [])
        self.assertEqual(len(self.list.due(now + datetime.timedelta(minutes=61))), 1)
        with self.assertRaises(ValueError):
            self.list.snooze(r["id"], 7)

    def test_month_ends_and_leap_days(self):
        self.assertEqual(step(datetime.date(2026, 1, 31), "month"), datetime.date(2026, 2, 28))
        self.assertEqual(step(datetime.date(2026, 12, 15), "month"), datetime.date(2027, 1, 15))
        self.assertEqual(step(datetime.date(2028, 2, 29), "year"), datetime.date(2029, 2, 28))

    def test_nonsense_is_refused(self):
        for entry in ({"text": "", "date": "2026-10-12"}, {"text": "x", "date": "12.10.2026"}, {"text": "x", "date": "2026-10-12", "time": "25:00"}):
            with self.assertRaises(ValueError):
                self.list.save(entry)
