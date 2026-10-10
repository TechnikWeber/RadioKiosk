import unittest

import numpy as np

from radiokiosk.qsolog import adif, as_csv, band_of, clean
from radiokiosk.sources.survey import analyse, as_text, noise_floor, own_oscillator, parse_sweep, ranges_for, service_at
from radiokiosk.spaceweather import nearest_sonde, parse_solar


class SurveyTest(unittest.TestCase):
    def sweeps(self, count=6):
        """144-146 MHz in 5 kHz slices: noise, a carrier that never leaves, and a station on 145.5 half of the time."""
        rng = np.random.default_rng(1)
        freqs = 144e6 + 5e3 * np.arange(401)
        rows = []
        for i in range(count):
            row = -60 + rng.normal(0, 1, len(freqs))
            row[100] = -30                       # 144.500, always
            if i % 2 == 0:
                row[299:302] = -35               # 145.495-145.505, every other sweep
                row[300] = -32
            rows.append(row)
        return freqs, rows

    def test_what_comes_and_goes_is_told_from_what_is_always_there(self):
        report = analyse(*self.sweeps(), 5e3)
        self.assertEqual([s["mhz"] for s in report["now_and_then"]], [145.5])
        self.assertEqual(report["now_and_then"][0]["share"], 0.5)
        self.assertEqual([s["mhz"] for s in report["suspects"]], [144.5])   # a steady carrier inside an amateur band
        calling = next(c for c in report["centres"] if c["mhz"] == 145.5)
        self.assertEqual(calling["share"], 0.5)
        self.assertEqual(next(c for c in report["centres"] if c["mhz"] == 144.3)["share"], 0)

    def test_the_report_reads_as_text(self):
        freqs, rows = self.sweeps()
        text = as_text({"range": "2m", "started": 0, "seconds": 12, **analyse(freqs, rows, 5e3)})
        self.assertIn("2 m FM calling", text)
        self.assertIn("active in 50 % of the sweeps", text)

    def test_the_floor_follows_a_step_in_the_noise_but_not_a_wide_transmission(self):
        levels = np.concatenate([np.full(4000, -60.0), np.full(4000, -50.0)])   # 100 MHz quiet, 100 MHz noisier
        levels[1000:1320] = -20                                                 # 8 MHz of television in the quiet part
        floor = noise_floor(levels, 25e3)
        self.assertAlmostEqual(floor[1160], -60, delta=1)
        self.assertAlmostEqual(floor[6000], -50, delta=1)

    def test_noise_at_the_threshold_is_not_a_transmission(self):
        freqs, rows = self.sweeps()
        for i, row in enumerate(rows):
            row[200] = -51 if i % 2 else -53     # 145.000: 9 or 7 dB over the floor, crossing the threshold
        report = analyse(freqs, rows, 5e3)
        self.assertEqual([s["mhz"] for s in report["now_and_then"]], [145.5])

    def test_what_only_one_tuning_shows_is_left_out(self):
        freqs, rows = self.sweeps(8)
        for i, row in enumerate(rows):
            row[299:302] = -35 if i in (0, 1, 4, 5) else row[298]   # the station now talks during both tunings
            if i % 2 == 0 or i == 3:
                row[50] = -30                    # 144.250: a spike of the stick, nearly only with the first tuning
        report = analyse(freqs, rows, 5e3, [i % 2 for i in range(8)])
        found = [s["mhz"] for key in ("now_and_then", "suspects", "steady") for s in report[key]]
        self.assertNotIn(144.25, found)
        self.assertEqual(report["ghosts"], 1)
        self.assertIn(144.5, found)              # the carrier that both tunings see stays

    def test_ranges_follow_the_stick(self):
        self.assertEqual(ranges_for(True)["all"][:2], (0.5e6, 1766e6))       # Blog V4: down into shortwave
        self.assertEqual(ranges_for(False)["all"][:2], (24e6, 1766e6))
        old = ranges_for(False, ("FC0013", 22, 1100))                        # an old DVB-T stick
        self.assertEqual(old["all"][:2], (22e6, 1100e6))
        self.assertEqual(old["uhf"][:2], (300e6, 1000e6))
        self.assertNotIn("2m", ranges_for(False, ("FC2580", 146, 924)))      # this tuner starts above the band

    def test_the_stick_hears_its_own_crystal(self):
        self.assertTrue(own_oscillator(28.806, 20))
        self.assertTrue(own_oscillator(144.0, 5))
        self.assertFalse(own_oscillator(145.5, 12.5))

    def test_one_sweep_cannot_call_anything_steady(self):
        freqs, rows = self.sweeps(1)
        self.assertEqual(analyse(freqs, rows, 5e3)["suspects"], [])

    def test_rtl_power_lines_become_one_sorted_sweep(self):
        freqs, levels = parse_sweep("2026-10-10, 10:00:00, 2000, 4000, 1000, 8, -40.0, -41.0\n"
                                    "garbage\n2026-10-10, 10:00:00, 0, 2000, 1000, 8, -50.0, nan\n")
        self.assertEqual(list(freqs), [0, 1000, 2000, 3000])
        self.assertEqual(list(levels), [-50.0, -120.0, -40.0, -41.0])

    def test_the_narrowest_service_names_a_frequency(self):
        self.assertEqual(service_at(433.92)[2], "ISM 433 MHz (remotes, sensors)")
        self.assertEqual(service_at(435.0)[2], "70 cm amateur")
        self.assertIsNone(service_at(300.0))


class LogTest(unittest.TestCase):
    def test_an_entry_is_tidied_and_its_band_found(self):
        entry = clean({"call": " dl1abc ", "mhz": "145.5", "mode": "FM", "locator": "jn48", "time": 1791612000})
        self.assertEqual((entry["call"], entry["band"], entry["locator"]), ("DL1ABC", "2m", "JN48"))
        self.assertEqual(band_of(7.1), "40m")
        for wrong in ({"call": "x"}, {"call": "DL1ABC", "mhz": "high"}):
            with self.assertRaises(ValueError):
                clean(wrong)

    def test_adif_and_csv(self):
        entry = clean({"call": "DL1ABC", "mhz": 145.5, "mode": "FM", "rst_sent": "59", "worked": "dk2xyz",
                       "notes": "nice chat", "time": 1791612000})
        text = adif([entry], "DL4PW", True)
        for part in ("<CALL:6>DL1ABC", "<QSO_DATE:8>20261010", "<TIME_ON:6>060000", "<BAND:2>2M", "<FREQ:8>145.5000",
                     "<COMMENT:24>worked DK2XYZ; nice chat", "<STATION_CALLSIGN:5>DL4PW", "<SWL:1>Y", "<EOR>"):
            self.assertIn(part, text)
        self.assertIn("2026-10-10,06:00,DL1ABC,2m,145.5,FM,59", as_csv([entry]))


SOLAR = b"""<solar><solardata><updated> 10 Oct 2026 0840 GMT</updated><solarflux>121</solarflux><aindex> 11</aindex>
<kindex> 3</kindex><xray>C2.4</xray><sunspots>99</sunspots><solarwind>416.9</solarwind><magneticfield> -0.8</magneticfield>
<calculatedconditions><band name="80m-40m" time="day">Poor</band><band name="30m-20m" time="night">Good</band>
</calculatedconditions><geomagfield>UNSETTLD</geomagfield><muf>NoRpt</muf></solardata></solar>"""


class SpaceWeatherTest(unittest.TestCase):
    def test_figures_and_band_conditions(self):
        solar = parse_solar(SOLAR)
        self.assertEqual((solar["flux"], solar["k"], solar["xray"], solar["bz"]), (121, 3, "C2.4", -0.8))
        self.assertEqual(solar["bands"][1], {"band": "30m-20m", "time": "night", "state": "good"})

    def test_the_nearest_ionosonde_that_reported_lately(self):
        stations = [
            {"station": {"name": "Dourbes", "latitude": "50.1", "longitude": "4.6"}, "mufd": 22.7, "fof2": 6.3,
             "time": "2026-10-10T06:00:00"},
            {"station": {"name": "Stale but close", "latitude": "48.8", "longitude": "9.2"}, "mufd": 30, "fof2": 9,
             "time": "2024-01-01T00:00:00"},
            {"station": {"name": "Austin", "latitude": "30.4", "longitude": "262.3"}, "mufd": 28, "fof2": 8,
             "time": "2026-10-10T06:00:00"},
        ]
        sonde = nearest_sonde(stations, (48.76, 9.16), now=1791612000 + 1800)
        self.assertEqual((sonde["name"], sonde["muf"], sonde["age"]), ("Dourbes", 22.7, 30))
