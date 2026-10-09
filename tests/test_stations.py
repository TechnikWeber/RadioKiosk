import unittest

from radiokiosk.favorites import Favorites, key
from radiokiosk.sources.fm import Fm


class FavoritesTest(unittest.TestCase):
    def test_star_twice_removes_again(self):
        favorites = Favorites()
        favorites.clear()
        entry = {"kind": "fm", "title": "94.30 MHz", "mhz": 94.3}
        self.assertEqual(len(favorites.toggle(entry)), 1)
        self.assertEqual(favorites.toggle({"kind": "fm", "title": "other title", "mhz": 94.30}), [])

    def test_same_frequency_in_another_mode_is_another_favorite(self):
        self.assertNotEqual(key({"kind": "tuner", "hz": 145500000, "mode": "nfm"}),
                            key({"kind": "tuner", "hz": 145500000, "mode": "usb"}))

    def test_retitle_follows_a_name_learned_later(self):
        favorites = Favorites()
        favorites.clear()
        favorites.toggle({"kind": "fm", "title": "94.30 MHz", "mhz": 94.3})
        favorites.retitle(("fm", "94.30"), "SWR3 · 94.30 MHz")
        self.assertEqual(favorites.items[0]["title"], "SWR3 · 94.30 MHz")


class FmScanTest(unittest.TestCase):
    def test_stations_are_the_peaks_above_the_noise(self):
        levels = [-30.0] * 410                 # 87.5 to 108 MHz in 50 kHz steps
        for mhz, db in ((91.8, 5.0), (94.3, -2.0), (94.4, -8.0)):   # 94.4 is the shoulder of 94.3
            levels[round((mhz - 87.5) / 0.05)] = db
        csv = "2026-01-01, 00:00:00, 87500000, 108000000, 50000.00, 1, " + ", ".join(map(str, levels))
        self.assertEqual([s["mhz"] for s in Fm._find_stations(csv)], [91.8, 94.3])
