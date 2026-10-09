"""RDS decoder: station name and radio text from the 57 kHz subcarrier of FM broadcast.

Input is the FM multiplex signal at 384 kHz; RDS sits on a 57 kHz carrier as
1187.5 bit/s biphase symbols. The chain: shift to baseband, find the carrier
phase, matched filter, bit timing, differential decoding, then block
synchronisation with the checkword syndromes from the RDS standard.
"""

import numpy as np

RATE = 384_000
DECIMATION = 16
SYMBOL_RATE = RATE / DECIMATION       # 24 kHz
BIT = SYMBOL_RATE / 1187.5            # samples per bit, not an integer
PHASES = 20                           # timing resolution within one bit

# Syndromes of the 26-bit blocks A, B, C, D and C' (generator polynomial 0x5B9)
POLY, CHECK_BITS = 0x5B9, 10
SYNDROMES = {383: "A", 14: "B", 303: "C", 663: "D", 748: "C'"}

# RDS uses its own character table; these differ from Latin-1 and matter in German
SPECIAL = {0x91: "ä", 0x97: "ö", 0x99: "ü", 0xD1: "Ä", 0xD7: "Ö", 0xD9: "Ü", 0x8E: "ß",
           0x82: "é", 0x83: "è", 0x8A: "ê", 0x80: "á", 0x81: "à"}


def syndrome(word):
    reg = 0
    for i in range(26 - 1, -1, -1):
        reg = (reg << 1) | ((word >> i) & 1)
        if reg & (1 << CHECK_BITS):
            reg ^= POLY
    for _ in range(CHECK_BITS):
        reg <<= 1
        if reg & (1 << CHECK_BITS):
            reg ^= POLY
    return reg & ((1 << CHECK_BITS) - 1)


def char(code):
    if code in SPECIAL:
        return SPECIAL[code]
    return chr(code) if 0x20 <= code < 0x7F else " "


class Rds:
    def __init__(self, lowpass):
        self.oscillator = np.exp(-2j * np.pi * 57e3 * np.arange(128) / RATE).astype(np.complex64)
        self.position = 0
        self.taps = lowpass(2.4e3, RATE, 97).astype(np.float32)
        self.tail = np.zeros(len(self.taps) - 1, np.complex64)
        self.carrier = 0j
        self.angle = 0.0
        # one bit is a positive and a negative half
        half = int(BIT // 2)
        self.matched = np.concatenate([np.ones(half), -np.ones(half)]).astype(np.float32)
        self.matched_tail = np.zeros(len(self.matched) - 1, np.float32)
        self.count = 0                     # samples seen at 24 kHz
        self.next_bit = BIT                # when to take the next bit decision
        self.energy = np.zeros(PHASES)
        self.last_sign = False
        self.bits = 0                      # shift register of decoded bits
        self.bit_number = 0
        self.blocks = {}                   # (block letter, bit number) -> data word
        self.pi = None
        self.name = [None] * 4
        self.text = {}
        self.text_flag = None
        self.info = {}

    def __call__(self, mpx):
        """Feed one block of multiplex samples; returns the station info when it changed."""
        osc = self.oscillator[(self.position + np.arange(len(mpx))) % 128]
        self.position = (self.position + len(mpx)) % 128
        data = np.concatenate([self.tail, mpx * osc])
        self.tail = data[len(mpx):]
        base = np.convolve(data, self.taps, "valid")[::DECIMATION]

        # BPSK squared has a constant phase: twice the carrier phase
        self.carrier = 0.95 * self.carrier + 0.05 * np.mean(base * base)
        angle = np.angle(self.carrier) / 2
        if np.cos(angle - self.angle) < 0:   # the halved angle is ambiguous by 180°; stay on one side
            angle += np.pi
        self.angle = angle
        signal = (base * np.exp(-1j * angle)).real.astype(np.float32)

        data = np.concatenate([self.matched_tail, signal])
        self.matched_tail = data[len(signal):]
        matched = np.convolve(data, self.matched[::-1], "valid")

        # bit timing: the matched filter output is strongest at the true bit boundaries
        index = self.count + np.arange(len(matched))
        phase = ((index % BIT) / BIT * PHASES).astype(int) % PHASES
        self.energy = 0.9 * self.energy + np.bincount(phase, matched * matched, PHASES)
        wanted = (np.argmax(self.energy) + 0.5) * BIT / PHASES
        error = (wanted - self.next_bit % BIT + BIT / 2) % BIT - BIT / 2
        self.next_bit += 0.15 * error

        changed = False
        end = self.count + len(matched)
        while round(self.next_bit) < end:
            sample = matched[max(0, round(self.next_bit) - self.count)]
            self.next_bit += BIT
            sign = bool(sample > 0)
            changed |= self._bit(sign != self.last_sign)   # differential coding
            self.last_sign = sign
        self.count = end
        if self.count > 1 << 40:
            self.count -= 1 << 40
            self.next_bit -= 1 << 40
        return dict(self.info) if changed else None

    def _bit(self, bit):
        self.bits = ((self.bits << 1) | bit) & 0x3FFFFFF
        self.bit_number += 1
        letter = SYNDROMES.get(syndrome(self.bits))
        if letter is None:
            return False
        # Shifted copies of a block can match a syndrome too, so remember every match by
        # position instead of only the latest one per letter.
        self.blocks[letter, self.bit_number] = self.bits >> CHECK_BITS
        if letter != "D":
            return False
        # a group is complete when A, B and C (or C') arrived exactly 26 bits apart before this D
        a = self.blocks.get(("A", self.bit_number - 78))
        b = self.blocks.get(("B", self.bit_number - 52))
        c = self.blocks.get(("C", self.bit_number - 26), self.blocks.get(("C'", self.bit_number - 26)))
        self.blocks = {key: word for key, word in self.blocks.items() if key[1] > self.bit_number - 104}
        if a is None or b is None:
            return False
        return self._group(a, b, c, self.bits >> CHECK_BITS)

    def _group(self, a, b, c, d):
        if a != self.pi:
            self.pi, self.name, self.text, self.text_flag = a, [None] * 4, {}, None
        group, version_b = b >> 12, (b >> 11) & 1
        before = dict(self.info)
        if group == 0:                                   # station name, two characters per group
            self.name[b & 3] = char(d >> 8) + char(d & 0xFF)
            if all(self.name):
                self.info["ps"] = "".join(self.name).strip()
        elif group == 2 and c is not None:               # radio text
            flag = (b >> 4) & 1
            if flag != self.text_flag:
                self.text, self.text_flag = {}, flag
            words = [d] if version_b else [c, d]
            codes = [code for w in words for code in (w >> 8, w & 0xFF)]
            self.text[b & 0xF] = "".join("\r" if code == 0x0D else char(code) for code in codes)
            parts = []
            for i in range(16):
                if i not in self.text:
                    break
                parts.append(self.text[i])
                if "\r" in self.text[i]:
                    break
            else:
                parts.append("\r")
            joined = "".join(parts)
            if "\r" in joined:
                self.info["text"] = joined.split("\r")[0].strip()
        self.info["pi"] = f"{a:04X}"
        return self.info != before
