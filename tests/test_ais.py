import unittest

from radiokiosk.sources.ais import Sentences, bits_of, decode


def armour(bits):
    """The reverse of bits_of(), to build sentences for the tests."""
    bits += "0" * (-len(bits) % 6)
    values = [int(bits[i:i + 6], 2) for i in range(0, len(bits), 6)]
    return "".join(chr(v + 48 if v < 40 else v + 56) for v in values)


def six_bit(text, length):
    return "".join(format(ord(c) - 64 if ord(c) >= 64 else ord(c), "06b") for c in text.ljust(length, "@"))


class AisTest(unittest.TestCase):
    def test_position_report_from_the_protocol_description(self):
        # the worked example of the AIVDM/AIVDO protocol description
        ship = decode(Sentences().feed("!AIVDM,1,1,,B,177KQJ5000G?tO`K>RA1wUbN0TKH,0*5C"))
        self.assertEqual(ship["mmsi"], 477553000)
        self.assertAlmostEqual(ship["lat"], 47.58283, places=4)
        self.assertAlmostEqual(ship["lon"], -122.34583, places=4)
        self.assertEqual((ship["speed"], ship["track"]), (0.0, 51.0))

    def test_a_name_split_over_two_sentences_is_put_together(self):
        bits = (format(5, "06b") + "00" + format(211234560, "030b") + "0" * 74
                + six_bit("SEEADLER", 20) + format(70, "08b") + "0" * 62 + six_bit("HAMBURG", 20) + "00")
        payload, sentences = armour(bits), Sentences()
        self.assertIsNone(sentences.feed(f"!AIVDM,2,1,3,A,{payload[:40]},0*00"))
        ship = decode(sentences.feed(f"!AIVDM,2,2,3,A,{payload[40:]},0*00"))
        self.assertEqual((ship["mmsi"], ship["name"], ship["destination"]), (211234560, "SEEADLER", "HAMBURG"))

    def test_positions_marked_not_available_are_left_out(self):
        bits = (format(1, "06b") + "00" + format(211000001, "030b") + "0" * 12 + format(1023, "010b") + "0"
                + format(181 * 600000, "028b") + format(91 * 600000, "027b") + format(3600, "012b") + "0" * 40)
        self.assertEqual(decode(bits), {"mmsi": 211000001})

    def test_other_lines_and_broken_sentences_are_ignored(self):
        sentences = Sentences()
        for line in ("Tuner gain set to 40.2 dB", "!AIVDM,x,1,,B,177,0*00", "!AIVDM,2,2,5,A,177KQJ,0*00", ""):
            self.assertIsNone(sentences.feed(line))
        self.assertIsNone(decode(bits_of("1")))
