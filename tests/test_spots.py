import unittest

from radiokiosk.spots import mode_in, parse_dxsummit, parse_hamqth, parse_pota


class SpotsTest(unittest.TestCase):
    def test_the_dx_cluster_as_hamqth_lists_it(self):
        spots = parse_hamqth("PD2WL^14084.0^LZ2NW^FT8 KN23 tnx^0946 2026-10-10^^^EU^20M^Bulgaria^212\n"
                             "broken line\nIW1FRU^high^YD1KLS^^0946 2026-10-10\n")
        self.assertEqual(len(spots), 1)
        spot = spots[0]
        self.assertEqual((spot["dx"], spot["khz"], spot["band"], spot["spotter"], spot["where"], spot["mode"]),
                         ("LZ2NW", 14084.0, "20m", "PD2WL", "Bulgaria", "FT8"))
        self.assertEqual(spot["time"], 1791625560)

    def test_the_fallback_and_the_parks(self):
        summit = parse_dxsummit([{"dx_call": "tm47cdxc", "frequency": 7173.0, "de_call": "F4DYK", "info": None,
                                 "time": "2026-10-10T09:46:28", "dx_country": "France"}, {"nothing": "useful"}])
        self.assertEqual([(s["dx"], s["band"], s["where"]) for s in summit], [("TM47CDXC", "40m", "France")])
        parks = parse_pota([{"activator": "9H6C", "frequency": "14080.0", "mode": "FT4", "reference": "MT-0007",
                             "name": "Is-Salini", "locationDesc": "MT-NO", "spotter": "LB9KJ", "comments": "",
                             "spotTime": "2026-10-10T09:23:47"}, {"activator": "X", "frequency": None}])
        self.assertEqual((parks[0]["dx"], parks[0]["mode"], parks[0]["where"]), ("9H6C", "FT4", "MT-0007 Is-Salini, MT-NO"))

    def test_the_mode_is_read_from_the_comment(self):
        self.assertEqual([mode_in("cq cw up 1"), mode_in("FT8 -12 dB"), mode_in("loud signal")], ["CW", "FT8", ""])
