"""Synthetic radio signals for the tests."""

import numpy as np

from radiokiosk.rds import POLY, RATE

OFFSET_WORDS = {"A": 252, "B": 408, "C": 360, "D": 436}


def checkword(data):
    reg = 0
    for i in range(15, -1, -1):
        reg = (reg << 1) | ((data >> i) & 1)
        if reg & 1024:
            reg ^= POLY
    for _ in range(10):
        reg <<= 1
        if reg & 1024:
            reg ^= POLY
    return reg & 1023


def rds_block(data, letter):
    return (data << 10) | (checkword(data) ^ OFFSET_WORDS[letter])


def rds_bits(pi, name, text, repeats=6):
    """Groups 0A (station name) and 2A (radio text), encoded as the standard says."""
    text = text + "\r"
    text += " " * (-len(text) % 4)
    bits = []

    def group(b, c, d):
        for word, letter in ((pi, "A"), (b, "B"), (c, "C"), (d, "D")):
            block = rds_block(word, letter)
            bits.extend((block >> i) & 1 for i in range(25, -1, -1))

    for _ in range(repeats):
        for i in range(4):
            group(i, 0xE0CD, (ord(name[2 * i]) << 8) | ord(name[2 * i + 1]))
        for i in range(len(text) // 4):
            part = text[4 * i:4 * i + 4]
            group(0x2000 | i, (ord(part[0]) << 8) | ord(part[1]), (ord(part[2]) << 8) | ord(part[3]))
    return bits


def fm_multiplex(bits, noise=0.02, seed=1):
    """What an FM demodulator outputs for a stereo station that also sends RDS."""
    differential = np.cumsum(bits) % 2
    per_bit = RATE / 1187.5
    n = np.arange(int(len(differential) * per_bit))
    index = (n / per_bit).astype(int)
    biphase = (2.0 * differential[index] - 1) * np.where(n / per_bit - index < 0.5, 1, -1)
    t = n / RATE
    audio = (0.4 * np.sin(2 * np.pi * 3000 * t)
             + 0.3 * np.sin(2 * np.pi * 38000 * t) * np.sin(2 * np.pi * 1200 * t)
             + 0.09 * np.sin(2 * np.pi * 19000 * t))
    rng = np.random.default_rng(seed)
    return (audio + 0.04 * biphase * np.cos(2 * np.pi * 57000 * t + 1.1)
            + rng.normal(0, noise, len(t))).astype(np.float32)


def tone_snr(audio, tone, rate=48000):
    """Power of `tone` relative to everything else in the audio band, in dB."""
    audio = audio[rate // 2:]
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio)))) ** 2
    f = np.fft.rfftfreq(len(audio), 1 / rate)
    wanted = spectrum[abs(f - tone) < 30].sum()
    rest = spectrum[(f > 100) & (f < 15000) & (abs(f - tone) >= 30)].sum()
    return 10 * np.log10(wanted / rest)
