import calendar
import unittest

from radiokiosk.schedule import Schedule, _on_day, seasons

CSV = """kHz:75;Time(UTC):93;Days:59;ITU:49;Station:201;Lng:49;Target:62;Remarks:135;P:35;Start:60;Stop:60;
77.5;0000-2400;;D;DCF77 time signal;-TS;Eu;;1;;
6070;0500-2100;;D;Channel 292;D,E;Eu;;1;;
6070;2100-0500;;CAN;CFRX Toronto;E;NAm;;1;;
6085;1000-1100;Sa,Su;D;Weekend Radio;D;Eu;;1;;
9670;0800-0900;Mo-Fr;D;Weekday Radio;D;Eu;;1;;
"""


def utc(day, hour, minute=0):
    """A moment in the week of Monday 2026-10-05."""
    return calendar.timegm((2026, 10, 5 + day, hour, minute, 0))


class ScheduleTest(unittest.TestCase):
    def setUp(self):
        self.schedule = Schedule()
        self.schedule.entries = Schedule.parse(CSV)

    def names(self, low, high, when):
        return [e["station"] for e in self.schedule.on_air(low, high, when)]

    def test_utility_stations_are_left_out(self):
        self.assertEqual(self.names(0, 30000, utc(0, 12)), ["Channel 292"])

    def test_times_that_run_past_midnight(self):
        self.assertEqual(self.names(6000, 6100, utc(0, 23)), ["CFRX Toronto"])
        self.assertEqual(self.names(6000, 6100, utc(0, 3)), ["CFRX Toronto"])

    def test_days_of_the_week(self):
        self.assertIn("Weekend Radio", self.names(6000, 6100, utc(5, 10, 30)))      # Saturday
        self.assertNotIn("Weekend Radio", self.names(6000, 6100, utc(2, 10, 30)))   # Wednesday
        self.assertEqual(self.names(9000, 10000, utc(4, 8, 30)), ["Weekday Radio"])  # Friday
        self.assertTrue(_on_day("135", 0) and not _on_day("135", 1))

    def test_season_code_follows_the_calendar(self):
        self.assertEqual(seasons(calendar.timegm((2026, 7, 1, 0, 0, 0)))[0], "a26")
        self.assertEqual(seasons(calendar.timegm((2026, 12, 1, 0, 0, 0)))[0], "b26")
        self.assertEqual(seasons(calendar.timegm((2027, 1, 15, 0, 0, 0)))[0], "b26")
