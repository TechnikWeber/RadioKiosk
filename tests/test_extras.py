import calendar
import unittest

from radiokiosk.alerts import parse as parse_alerts
from radiokiosk.audiobooks import chapters_of
from radiokiosk.satellites import look_angles, parse_elements, passes
from radiokiosk.sources.aprs import packet, position

ASTRA = ("1 37775U 11041A   26282.95360937  .00000111  00000+0  00000+0 0  9999",
         "2 37775   0.1164  50.9424 0003670 123.3044 206.8366  1.00272827 45672")
ISS = ("1 25544U 98067A   26282.82140208  .00006479  00000+0  12652-3 0  9999",
       "2 25544  51.6314  92.7969 0006774 242.6225 117.4075 15.48793003589525")
MIDNIGHT = calendar.timegm((2026, 10, 10, 0, 0, 0))


class SatelliteTest(unittest.TestCase):
    def test_a_television_satellite_stands_where_every_dish_points(self):
        # Astra at 19.2 degrees east: from Stuttgart about 33 degrees up, a little east of south, all day
        for hour in (0, 6, 12, 18):
            elevation, azimuth = look_angles(ASTRA, 48.78, 9.18, [MIDNIGHT + hour * 3600])
            self.assertAlmostEqual(float(elevation[0]), 33.2, delta=0.5)
            self.assertAlmostEqual(float(azimuth[0]), 166.8, delta=0.5)

    def test_passes_of_the_space_station(self):
        found = passes({25544: ISS}, 48.78, 9.18, MIDNIGHT)
        self.assertTrue(3 <= len(found) <= 8)
        for one in found:
            self.assertEqual(one["name"], "ISS")
            self.assertTrue(120 <= one["set"] - one["rise"] <= 700)   # a pass lasts a few minutes
            self.assertTrue(10 <= one["highest"] <= 90)
        self.assertEqual(sorted(p["rise"] for p in found), [p["rise"] for p in found])

    def test_only_the_listed_satellites_are_kept(self):
        text = "ISS (ZARYA)\n" + "\n".join(ISS) + "\nSOMETHING ELSE\n1 99999U 00000A   26282.0  .0  0  0 0  9990\n2 99999 0 0 0 0 0 1.0 0\n"
        self.assertEqual(list(parse_elements(text)), [25544])


class AprsTest(unittest.TestCase):
    def test_the_three_ways_to_send_a_position(self):
        # the worked examples of the APRS protocol reference
        plain = position("APRS", "!4903.50N/07201.75W-Test")
        self.assertEqual((plain["lat"], plain["lon"], plain["comment"]), (49.05833, -72.02917, "Test"))
        stamped = position("APRS", "@092345z4903.50N/07201.75W>Test")
        self.assertEqual((stamped["lat"], stamped["lon"]), (49.05833, -72.02917))
        packed = position("APRS", "=/5L!!<*e7>7P[")
        self.assertAlmostEqual(packed["lat"], 49.5, places=2)
        self.assertAlmostEqual(packed["lon"], -72.75, places=2)
        # Mic-E: 33 25.64 N in the destination, whose fifth letter also adds 100 degrees to the longitude
        mic_e = position("S32UVT", "`(_fn\"Oj/")
        self.assertAlmostEqual(mic_e["lat"], 33 + 25.64 / 60, places=4)
        self.assertAlmostEqual(mic_e["lon"], -(112 + 7.74 / 60), places=4)

    def test_a_line_of_the_decoder(self):
        station = packet("[0.3] DL1ABC-9>APDR16,WIDE1-1,qAR,DB0XYZ:=4846.45N/00913.01E$ on the road")
        self.assertEqual((station["call"], station["lat"], station["lon"]), ("DL1ABC-9", 48.77417, 9.21683))
        for line in ("Dire Wolf version 1.7", "[0.3] DL1ABC>APRS:>status text only", "[0.3] DL1ABC>APRS:!broken"):
            self.assertIsNone(packet(line))


class OtherTest(unittest.TestCase):
    def test_warnings_in_force_the_severe_ones_first(self):
        data = {"alerts": [
            {"severity": "minor", "onset": "2026-10-10T10:00:00+02:00", "expires": "2026-10-10T20:00:00+02:00",
             "headline_de": "Amtliche Warnung vor WINDBÖEN", "event_de": "WINDBÖEN"},
            {"severity": "severe", "onset": "2026-10-10T12:00:00+02:00", "expires": "2026-10-10T18:00:00+02:00",
             "headline_de": "Amtliche Unwetterwarnung vor ORKANBÖEN"},
            {"severity": "moderate", "onset": "2026-10-09T10:00:00+02:00", "expires": "2026-10-09T12:00:00+02:00",
             "headline_de": "abgelaufen"}]}
        found = parse_alerts(data, now=calendar.timegm((2026, 10, 10, 9, 0, 0)))
        self.assertEqual([a["headline_de"] for a in found],
                         ["Amtliche Unwetterwarnung vor ORKANBÖEN", "Amtliche Warnung vor WINDBÖEN"])
        self.assertEqual(found[1]["from"], calendar.timegm((2026, 10, 10, 8, 0, 0)))

    def test_chapters_of_a_book_in_reading_order_and_small_files(self):
        book = chapters_of("holmes", {"metadata": {"title": "Holmes"}, "files": [
            {"name": "h_02.mp3", "format": "VBR MP3", "title": "02", "length": "3546.64"},
            {"name": "h_02_64kb.mp3", "format": "64Kbps MP3", "title": "02 - League", "length": "59:06"},
            {"name": "h_01_64kb.mp3", "format": "64Kbps MP3", "title": "01 - Scandal", "length": "65:06"},
            {"name": "cover.jpg", "format": "JPEG"}]})
        self.assertEqual([(c["title"], c["seconds"]) for c in book["episodes"]], [("01 - Scandal", 3906), ("02 - League", 3546)])
        self.assertEqual(book["episodes"][0]["audio"], "https://archive.org/download/holmes/h_01_64kb.mp3")
