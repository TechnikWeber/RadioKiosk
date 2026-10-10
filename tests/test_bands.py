"""The band plan is data written by hand; a slip in it should not reach the receiver."""

import unittest

from radiokiosk.sources.tuner import BANDS, MODES


class BandPlan(unittest.TestCase):
    def test_every_entry_can_be_tuned(self):
        for band in BANDS:
            self.assertIn(band["mode"], MODES)
            self.assertTrue(band["presets"], band["id"])
            seen = set()
            for preset in band["presets"]:
                mode = preset.get("mode", band["mode"])
                self.assertIn(mode, MODES)
                self.assertTrue(100e3 <= preset["hz"] <= 1.75e9, preset)
                self.assertNotIn((preset["hz"], mode), seen, preset)   # favourites tell entries apart by these two
                seen.add((preset["hz"], mode))

    def test_cb_has_all_eighty_channels(self):
        cb = next(band for band in BANDS if band["id"] == "cb")
        numbered = [p for p in cb["presets"] if isinstance(p["name"], dict) and p["name"]["en"].startswith("Channel ")]
        self.assertEqual(len(numbered), 80)
        self.assertEqual({p["hz"] for p in numbered if p["name"]["en"] in ("Channel 23", "Channel 41")}, {27255000, 26565000})
