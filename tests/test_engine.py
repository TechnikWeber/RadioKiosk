import unittest

import numpy as np

from radiokiosk import engine

from .signals import tone_snr


class DemodulatorTest(unittest.TestCase):
    def test_fm_stereo_keeps_left_and_right_apart(self):
        for profile in (engine.WIDE, engine.LIGHT):
            with self.subTest(profile=profile):
                self.check_stereo(profile)

    def check_stereo(self, profile):
        rate = round(profile.wfm_bins * engine.BIN)
        size = profile.wfm_bins * 3 // 4
        t = np.arange(rate) / rate
        left = 0.5 * np.sin(2 * np.pi * 1000 * t)          # right channel stays silent
        mpx = left / 2 * 0.9 + left / 2 * 0.9 * np.sin(2 * np.pi * 38000 * t + 1.4) \
            + 0.1 * np.sin(2 * np.pi * 19000 * t + 0.7)
        signal = np.exp(2j * np.pi * 75e3 * np.cumsum(mpx) / rate).astype(np.complex64)
        wfm = engine.Wfm(profile)
        wfm.audio_mode = "stereo"
        out = np.concatenate([wfm(signal[i:i + size]) for i in range(0, len(signal) - size, size)])[24000:]
        self.assertTrue(wfm.stereo)
        self.assertGreater(out[:, 0].std(), 0.2)
        self.assertLess(out[:, 1].std(), 0.01)

    def test_mono_setting_wins_over_a_pilot_tone(self):
        rate = 384_000   # the wide profile's FM channel
        t = np.arange(rate // 4) / rate
        signal = np.exp(2j * np.pi * 75e3 * np.cumsum(0.1 * np.sin(2 * np.pi * 19000 * t)) / rate).astype(np.complex64)
        wfm = engine.Wfm()
        wfm.audio_mode = "mono"
        for i in range(0, len(signal) - 6144, 6144):
            wfm(signal[i:i + 6144])
        self.assertFalse(wfm.stereo)


class EngineTest(unittest.TestCase):
    """The whole chain from raw samples to audio, with a stand-in for the stick."""

    def run_engine(self, mode, iq, offset, profile):
        audio = []

        class NoStick:
            def __getattr__(self, name):
                return lambda *args: None

        original = engine.RtlSdr, engine.send
        engine.RtlSdr = lambda rate: NoStick()
        engine.send = lambda kind, payload: audio.append(np.frombuffer(payload, "<i2")) if kind == b"A" else None
        try:
            e = engine.Engine(28.0, True, profile)
            e.apply({"hz": 100_000_000, "mode": mode})
            e.apply({"hz": 100_000_000 + offset, "mode": mode})   # tuned away from the centre
            raw = np.empty(2 * len(iq), np.uint8)
            raw[0::2] = np.clip(iq.real * 60 + 127.5, 0, 255)
            raw[1::2] = np.clip(iq.imag * 60 + 127.5, 0, 255)
            for i in range(0, len(raw) - 2 * e.step, 2 * e.step):
                e.process(raw[i:i + 2 * e.step].tobytes())
        finally:
            engine.RtlSdr, engine.send = original
        return np.concatenate(audio).reshape(-1, 2)[:, 0] / 32768

    def test_blocks_join_without_clicks(self):
        """A clean tone must come out clean: seams between FFT blocks would show up as noise."""
        # offsets the stick is not retuned for: the channel sits away from the centre
        for profile, offsets in ((engine.WIDE, (200_000, -333_333)), (engine.LIGHT, (30_000, -41_111))):
            rate = profile.rate
            t = np.arange(2 * rate) / rate
            tone = np.sin(2 * np.pi * 1000 * t)
            for offset in offsets:
                with self.subTest(profile=profile, offset=offset):
                    carrier = 2 * np.pi * offset * t
                    wide = np.exp(1j * (carrier + 2 * np.pi * 50e3 * np.cumsum(tone) / rate))
                    narrow = np.exp(1j * (carrier + 2 * np.pi * 2.5e3 * np.cumsum(tone) / rate))
                    self.assertGreater(tone_snr(self.run_engine("wfm", wide, offset, profile), 1000), 55)
                    self.assertGreater(tone_snr(self.run_engine("nfm", narrow, offset, profile), 1000), 40)
