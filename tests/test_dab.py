import unittest

from radiokiosk.sources.dab import reception


class ReceptionTest(unittest.TestCase):
    def test_bars_follow_the_signal_to_noise_ratio(self):
        self.assertEqual([reception(snr, 0) for snr in (2, 6, 9, 15)], [1, 2, 3, 4])

    def test_broken_frames_cost_bars_even_at_a_good_ratio(self):
        self.assertEqual(reception(15, 3), 2)
        self.assertEqual(reception(15, 40), 1)
