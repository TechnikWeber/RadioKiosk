import calendar
import unittest

from radiokiosk.schedule import Schedule, _joined, _on_day, seasons

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


LIST = """kHz;Time;Days;ITU;Station;Lng;Target;Remarks;P;Start;Stop;
6070;0000-2400;;D;Channel 292;D,E;Eu;;1;;
9600;1800-1900;;CHN;China Radio Int.;E;Eu;;1;;
9600;2000-2100;;CHN;China Radio Int.;E;Eu;;1;;
9600;2100-2200;;CHN;China Radio Int.;E;Eu;;1;;
9480;1800-2000;;CHN;China Radio Int.;F;Eu;;1;;
9570;1800-1900;;ROU;Radio Romania DIGITAL;D;CEu;;1;;
7646;0000-2400;;D;DWD 1 Pinneberg RTTY;E;Eu;;1;;
7400;1652-2050;31May;HOL;Free Radio Sce Holland;E;Eu;;1;;
5505;0000-2400;;IRL;Shannon Volmet;E;Eu;;1;;
6185;0000-2400;;MEX;Radio Educacion;S;CAm;;1;;
"""


class BroadcastsTest(unittest.TestCase):
    def setUp(self):
        self.schedule = Schedule()
        self.schedule.entries = Schedule.parse(LIST)

    def test_groups_hold_what_can_be_listened_to(self):
        found = self.schedule.broadcasts(utc(0, 20, 30))
        self.assertEqual([r["station"] for r in found["german"]], ["Channel 292"])
        self.assertEqual([(r["khz"], r["times"], r["now"]) for r in found["english"]],
                         [(9600, [[1800, 1900, ""], [2000, 2200, ""]], True)])
        self.assertEqual([(r["station"], r["language"], r["now"]) for r in found["others"]],
                         [("China Radio Int.", "F", False)])

    def test_hours_are_joined(self):
        self.assertEqual(_joined([[0, 300, ""], [0, 400, ""], [400, 2200, ""]]), [[0, 2200, ""]])
        self.assertEqual(_joined([[2000, 2300, ""], [2300, 100, ""]]), [[2000, 100, ""]])
        self.assertEqual(_joined([[800, 900, ""], [800, 900, "Sa"]]), [[800, 900, ""], [800, 900, "Sa"]])
