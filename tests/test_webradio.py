"""Web radio genres: one provider with many channels does not fill the top of a list."""

import unittest

from radiokiosk.sources.webradio import PER_PROVIDER, provider, spread


def station(name, homepage="", url=""):
    return {"name": name, "homepage": homepage, "url": url}


class Providers(unittest.TestCase):
    def test_provider_is_the_domain(self):
        self.assertEqual(provider(station("a", "https://plus.rm.fm/x")), "rm.fm")
        self.assertEqual(provider(station("b", "http://www.bbc.co.uk/radio")), "bbc.co.uk")
        self.assertEqual(provider(station("c", "", "https://stream.ella-radio.de/jazz")), "ella-radio.de")
        self.assertEqual(provider(station("d")), "")

    def test_a_providers_extra_channels_go_to_the_end(self):
        many = [station(f"0R {i}", "https://plus.rm.fm") for i in range(PER_PROVIDER + 2)]
        others = [station("WDR 3", "https://www1.wdr.de"), station("NDR Blue", "https://www.ndr.de")]
        rows, moved = spread(many[:4] + others[:1] + many[4:] + others[1:])
        self.assertEqual(moved, 2)
        self.assertEqual([s["name"] for s in rows], ["0R 0", "0R 1", "0R 2", "WDR 3", "NDR Blue", "0R 3", "0R 4"])

    def test_stations_without_a_provider_stay_in_place(self):
        rows, moved = spread([station(str(i)) for i in range(6)])
        self.assertEqual((moved, [s["name"] for s in rows]), (0, [str(i) for i in range(6)]))


if __name__ == "__main__":
    unittest.main()
