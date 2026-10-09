import unittest

from radiokiosk.engine import lowpass
from radiokiosk.rds import SYNDROMES, Rds, syndrome

from .signals import fm_multiplex, rds_bits, rds_block


class RdsTest(unittest.TestCase):
    def test_syndromes_identify_the_blocks(self):
        for letter in "ABCD":
            self.assertEqual(SYNDROMES[syndrome(rds_block(0x1234, letter))], letter)

    def test_name_and_text_are_decoded_from_a_noisy_signal(self):
        mpx = fm_multiplex(rds_bits(0xD3C3, "TESTFUNK", "Hallo Welt, das ist ein RDS-Test"))
        decoder, info = Rds(lowpass), {}
        for i in range(0, len(mpx) - 6144, 6144):
            info = decoder(mpx[i:i + 6144]) or info
        self.assertEqual(info, {"pi": "D3C3", "ps": "TESTFUNK", "text": "Hallo Welt, das ist ein RDS-Test"})
