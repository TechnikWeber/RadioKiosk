import datetime
import unittest

from radiokiosk.agenda import upcoming

FILE = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:a
DTSTART;VALUE=DATE:20261013
DTEND;VALUE=DATE:20261014
SUMMARY:Gelber Sack
END:VEVENT
BEGIN:VEVENT
UID:b
DTSTART;TZID=Europe/Berlin:20261005T183000
DTEND;TZID=Europe/Berlin:20261005T200000
RRULE:FREQ=WEEKLY;BYDAY=MO,TH;UNTIL=20261020T000000Z
EXDATE;TZID=Europe/Berlin:20261012T183000
SUMMARY:Training\\, Halle
LOCATION:Sporthalle
END:VEVENT
BEGIN:VEVENT
UID:c
DTSTART;VALUE=DATE:20260130
RRULE:FREQ=MONTHLY;BYDAY=-1FR
SUMMARY:Stammtisch
 am Abend
END:VEVENT
BEGIN:VEVENT
UID:d
DTSTART:20261014T100000Z
RRULE:FREQ=DAILY;COUNT=3
SUMMARY:Kurs
END:VEVENT
BEGIN:VEVENT
UID:d
RECURRENCE-ID:20261015T100000Z
DTSTART:20261015T150000Z
SUMMARY:Kurs verlegt
END:VEVENT
BEGIN:VEVENT
UID:e
DTSTART;VALUE=DATE:20261016
STATUS:CANCELLED
SUMMARY:Abgesagt
END:VEVENT
END:VCALENDAR
"""


class ReadingCalendars(unittest.TestCase):
    def setUp(self):
        since = datetime.datetime(2026, 10, 11)
        self.events = upcoming(FILE, since, since + datetime.timedelta(days=30))
        self.titles = [(e["start"][:10], e["title"]) for e in self.events]

    def test_an_all_day_event_keeps_its_day(self):
        event = next(e for e in self.events if e["title"] == "Gelber Sack")
        self.assertEqual((event["start"], event["all_day"]), ("2026-10-13T00:00", True))

    def test_weekly_repeats_stop_and_leave_out_their_exceptions(self):
        days = [day for day, title in self.titles if title == "Training, Halle"]
        self.assertEqual(days, ["2026-10-15", "2026-10-19"])

    def test_the_last_friday_of_the_month_and_a_folded_line(self):
        self.assertIn(("2026-10-30", "Stammtischam Abend"), self.titles)

    def test_a_moved_date_replaces_the_one_of_the_series(self):
        course = [(e["start"], e["title"]) for e in self.events if e["title"].startswith("Kurs")]
        self.assertEqual([title for _, title in course], ["Kurs", "Kurs verlegt", "Kurs"])
        self.assertEqual(len({start[:10] for start, _ in course}), 3)

    def test_a_daily_event_that_began_long_ago_still_reaches_today(self):
        old = "BEGIN:VEVENT\nUID:x\nDTSTART:20080101T070000\nRRULE:FREQ=DAILY\nSUMMARY:Morning\nEND:VEVENT\n"
        weekly = "BEGIN:VEVENT\nUID:y\nDTSTART:20050103T190000\nRRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO\nSUMMARY:Club\nEND:VEVENT\n"
        since = datetime.datetime(2026, 10, 11)
        found = upcoming(old + weekly, since, since + datetime.timedelta(days=14))
        self.assertEqual(len([e for e in found if e["title"] == "Morning"]), 14)
        club = [e["start"][:10] for e in found if e["title"] == "Club"]
        self.assertEqual(len(club), 1)
        self.assertEqual((datetime.date.fromisoformat(club[0]) - datetime.date(2005, 1, 3)).days % 14, 0)

    def test_cancelled_events_are_left_out(self):
        self.assertNotIn("Abgesagt", [title for _, title in self.titles])


if __name__ == "__main__":
    unittest.main()
