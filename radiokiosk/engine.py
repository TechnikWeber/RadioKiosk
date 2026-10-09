"""Receiver engine: owns the SDR stick, demodulates and computes the spectrum.

Runs as its own process (`python -m radiokiosk.engine`) so heavy signal
processing never blocks the web service.

  stdin   one JSON object per line:
          {"hz": ..., "mode": ..., "squelch": dB, "zoom": n, "stereo": "auto" | "stereo" | "mono"}
  stdout  frames of [1 byte kind][uint32 length][payload]
            A  audio, 48 kHz stereo signed 16 bit
            R  station name and radio text (RDS) as JSON, whenever they change
            S  spectrum, see SPECTRUM_HEADER, followed by WIDTH bytes (0..255 = -120..0 dBFS)
            E  error text

One FFT per block does three jobs: it is the waterfall, and picking the bins
around the tuned frequency and transforming them back is filter, frequency
shift and sample rate reduction in a single step (overlap-save).
"""

import argparse
import json
import queue
import struct
import sys
import threading

import numpy as np

from .gain import TUNER_GAINS
from .rds import Rds
from .rtlsdr import RtlSdr
from .util import sdr_devices

# Rate and block sizes are powers of two times the audio rate: the FFTs stay
# fast and every channel comes out at a whole multiple of 48 kHz.
RATE = 1_536_000          # samples per second from the stick
BLOCK = 32_768            # FFT size, about 47 Hz per bin
OVERLAP = BLOCK // 4      # carried over from the previous block
STEP = BLOCK - OVERLAP    # new samples per block (16 ms)
BIN = RATE / BLOCK
AUDIO = 48_000
WIDTH = 1024              # points per spectrum line
SPECTRUM_EVERY = 6        # blocks per spectrum line (about 10 lines per second)
ZOOMS = (1, 4, 16, 64)
RETUNE_BEYOND = 550_000   # retune the stick when the wanted frequency leaves this window
DIRECT_SAMPLING_BELOW = 24e6
SPECTRUM_HEADER = "<dddfffB"   # start Hz, span Hz, tuned Hz, level dBFS, SNR dB, gain dB, flags
FLAG_STEREO, FLAG_SQUELCHED = 1, 2
STEREO_ABOVE = 34         # dB of signal above the noise needed to switch to stereo


def lowpass(cutoff, rate, taps):
    n = np.arange(taps) - (taps - 1) / 2
    h = np.sinc(2 * cutoff / rate * n) * np.hamming(taps)
    return h / h.sum()


def decay(seconds, rate):
    """One-pole lowpass (de-emphasis) as a short FIR kernel."""
    a = 1 - np.exp(-1 / (rate * seconds))
    return a * (1 - a) ** np.arange(int(6 * seconds * rate) + 1)


def band_mask(offsets, low, high, edge):
    ramp = np.clip((offsets - low) / edge + 0.5, 0, 1) * np.clip((high - offsets) / edge + 0.5, 0, 1)
    return (0.5 - 0.5 * np.cos(np.pi * ramp)).astype(np.float32)


class Fir:
    """FIR filter that keeps its state between blocks."""

    def __init__(self, taps):
        self.taps = np.asarray(taps, np.float32)
        self.tail = np.zeros(len(self.taps) - 1, np.float32)

    def __call__(self, x):
        data = np.concatenate([self.tail, x])
        self.tail = data[len(x):]
        return np.convolve(data, self.taps, "valid")


class Discriminator:
    """FM demodulator: phase difference between consecutive samples."""

    def __init__(self):
        self.last = np.complex64(1)

    def __call__(self, x):
        previous = np.concatenate([[self.last], x[:-1]])
        self.last = x[-1]
        return np.angle(x * np.conj(previous)).astype(np.float32)


class Wfm:
    """Broadcast FM with stereo. Channel arrives at 384 kHz."""
    bins = 8192
    passband = (-100e3, 100e3, 30e3)

    def __init__(self):
        rate = RATE * self.bins // BLOCK
        self.scale = rate / (2 * np.pi * 75e3)
        self.disc = Discriminator()
        # 50 µs de-emphasis as used in Europe; the 19 kHz pilot must not reach the speakers
        final = np.convolve(lowpass(17e3, AUDIO, 41), decay(50e-6, AUDIO))
        self.decimation = rate // AUDIO
        self.sum_filters = Fir(lowpass(24e3, rate, 71)), Fir(final)
        self.diff_filters = Fir(lowpass(24e3, rate, 71)), Fir(final)
        # 19 kHz repeats exactly every 384 samples at this rate
        self.oscillator = np.exp(2j * np.pi * 19e3 * np.arange(384) / rate).astype(np.complex64)
        self.position = 0
        self.pilot = 0j
        self.stereo = False
        self.quality = 0.0     # signal above noise in dB, set by the engine
        self.audio_mode = "auto"   # or "stereo" / "mono" to override the automatic choice
        self.rds = Rds(lowpass)
        self.news = None       # station info, when it just changed

    def _audio(self, filters, x):
        return filters[1](filters[0](x)[::self.decimation])

    def __call__(self, x):
        mpx = self.disc(x) * self.scale
        osc = self.oscillator[(self.position + np.arange(len(mpx))) % 384]
        self.position = (self.position + len(mpx)) % 384
        # the pilot is A*sin(wt + p); its average against exp(-jwt) is A/2j * exp(jp)
        self.pilot = 0.8 * self.pilot + 0.2 * np.mean(mpx * np.conj(osc))
        level = abs(self.pilot)
        self.stereo = self.audio_mode != "mono" and level > (0.012 if self.stereo else 0.025)
        if self.audio_mode == "auto":
            # Stereo adds about 20 dB of hiss, so it is only worth it on a strong signal
            self.stereo &= self.quality > (STEREO_ABOVE - 4 if self.stereo else STEREO_ABOVE)
        self.news = self.rds(mpx)
        mono = self._audio(self.sum_filters, mpx)
        if not self.stereo:
            return np.stack([mono, mono], axis=1) * 0.8
        # L-R sits on sin(2(wt + p)), the pilot doubled
        carrier = (osc * (1j * self.pilot / level)) ** 2
        diff = self._audio(self.diff_filters, mpx * carrier.imag * 2)
        return np.stack([mono + diff, mono - diff], axis=1) * 0.8


class Nfm:
    """Narrow FM voice. Channel arrives at 48 kHz."""
    bins = 1024
    passband = (-6e3, 6e3, 1.5e3)

    def __init__(self):
        self.disc = Discriminator()
        self.scale = AUDIO / (2 * np.pi * 5e3)
        # voice radios pre-emphasise by 6 dB per octave; undo it and cut above 3.5 kHz
        self.filter = Fir(np.convolve(lowpass(3.5e3, AUDIO, 65), decay(1 / (2 * np.pi * 400), AUDIO)) * 4)
        self.stereo = False

    def __call__(self, x):
        return self.filter(self.disc(x) * self.scale)


class Am:
    bins = 1024
    passband = (-4.5e3, 4.5e3, 1e3)

    def __init__(self):
        self.carrier = 0.0
        self.stereo = False

    def __call__(self, x):
        envelope = np.abs(x)
        previous = self.carrier or float(envelope.mean())
        self.carrier = 0.9 * previous + 0.1 * float(envelope.mean())
        # dividing by the carrier level is the automatic volume control
        carrier = np.linspace(previous, self.carrier, len(x), dtype=np.float32)
        return (envelope - carrier) / np.maximum(carrier, 1e-9) * 0.7


class Ssb:
    bins = 1024

    def __init__(self, upper):
        self.passband = (150, 2900, 200) if upper else (-2900, -150, 200)
        self.level = 0.0
        self.gain = 1.0
        self.stereo = False

    def __call__(self, x):
        audio = x.real * 2
        rms = float(np.sqrt(np.mean(audio ** 2))) + 1e-9
        # automatic volume: react at once to loud signals, recover slowly
        self.level = rms if rms > self.level else 0.97 * self.level + 0.03 * rms
        gain = min(0.15 / self.level, 1e5)
        ramp = np.linspace(self.gain, gain, len(audio), dtype=np.float32)
        self.gain = gain
        return audio * ramp


MODES = {"wfm": Wfm, "nfm": Nfm, "am": Am, "usb": lambda: Ssb(True), "lsb": lambda: Ssb(False)}


def send(kind, payload):
    sys.stdout.buffer.write(kind + struct.pack("<I", len(payload)) + payload)
    sys.stdout.buffer.flush()


class Engine:
    def __init__(self, gain, fixed_gain):
        self.sdr = RtlSdr(RATE)
        devices = sdr_devices()
        self.needs_direct_sampling = bool(devices) and not devices[0]["v4"]
        self.direct = False
        self.sdr.reset()
        self.gain_index = min(range(len(TUNER_GAINS)), key=lambda i: abs(TUNER_GAINS[i] - gain))
        self.fixed_gain = fixed_gain
        self.sdr.set_gain(gain if fixed_gain else TUNER_GAINS[self.gain_index])
        self.center = None
        self.hz = None
        self.mode = None
        self.squelch = 0.0
        self.zoom = 1
        self.demod = None
        self.block = np.zeros(BLOCK, np.complex64)
        self.blocks = 0
        self.power = np.zeros(BLOCK, np.float32)
        self.raw_level = []
        self.snr = 0.0
        self.level = -120.0
        self.squelched = False
        self.commands = queue.Queue()
        self.samples = queue.Queue(maxsize=64)

    # --- input threads ---------------------------------------------------

    def read_commands(self):
        for line in sys.stdin:
            try:
                self.commands.put(json.loads(line))
            except ValueError:
                pass
        self.commands.put(None)   # the service went away

    def read_samples(self):
        try:
            while True:
                raw = self.sdr.read(2 * STEP)
                if len(raw) != 2 * STEP:
                    continue
                try:
                    self.samples.put_nowait(raw)
                except queue.Full:
                    pass   # too slow: drop a block instead of lagging behind
        except RuntimeError as e:
            self.samples.put(e)

    # --- tuning ----------------------------------------------------------

    def apply(self, command):
        hz, mode = int(command["hz"]), command["mode"]
        self.squelch = float(command.get("squelch", 0))
        self.zoom = command.get("zoom", 1) if command.get("zoom", 1) in ZOOMS else 1
        if self.center is None or abs(hz - self.center) > RETUNE_BEYOND:
            direct = self.needs_direct_sampling and hz < DIRECT_SAMPLING_BELOW
            if direct != self.direct:
                self.sdr.set_direct_sampling(direct)
                self.direct = direct
            self.center = hz
            self.sdr.set_frequency(hz)
            self.power[:] = 0
        if mode != self.mode or hz != self.hz:
            self.demod = MODES[mode]()   # a fresh demodulator also forgets the previous station's RDS
            self.mode = mode
        if mode == "wfm":
            self.demod.audio_mode = command.get("stereo", "auto")
        self.hz = hz
        self.blocks = 0
        bins = self.demod.bins
        self.offset_bins = round((hz - self.center) / BIN)
        centred = np.arange(-bins // 2, bins // 2)
        self.select = np.fft.ifftshift((self.offset_bins + centred) % BLOCK)
        self.mask = np.fft.ifftshift(band_mask(centred * BIN, *self.demod.passband)) * (bins / BLOCK)
        self.skip = OVERLAP * bins // BLOCK
        low, high, _ = self.demod.passband
        self.channel = slice(BLOCK // 2 + self.offset_bins + int(low / BIN),
                             BLOCK // 2 + self.offset_bins + int(high / BIN) + 1)

    # --- per block -------------------------------------------------------

    def process(self, raw):
        u8 = np.frombuffer(raw, np.uint8)
        probe = u8[::8]
        self.raw_level.append((float(np.sqrt(np.mean((probe.astype(np.float32) - 127.5) ** 2))),
                               np.count_nonzero((probe == 0) | (probe == 255)) / len(probe)))
        self.block[:OVERLAP] = self.block[STEP:]
        self.block[OVERLAP:] = ((u8.astype(np.float32) - 127.5) * (1 / 127.5)).view(np.complex64)
        spectrum = np.fft.fft(self.block)
        self.power += spectrum.real ** 2 + spectrum.imag ** 2

        channel = np.fft.ifft(spectrum[self.select] * self.mask)[self.skip:]
        # shifting by whole bins restarts its phase every block; undo that so blocks join seamlessly
        channel *= np.complex64(np.exp(-0.5j * np.pi * ((3 * self.offset_bins * self.blocks) % 4)))
        self.demod.quality = self.snr
        audio = self.demod(channel)
        if getattr(self.demod, "news", None):
            send(b"R", json.dumps({**self.demod.news, "hz": self.hz}).encode())
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        if self.squelched:
            audio = np.zeros_like(audio)
        send(b"A", (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())

        self.blocks += 1
        if self.blocks % SPECTRUM_EVERY == 0:
            self.send_spectrum()
        if self.blocks % (5 * SPECTRUM_EVERY) == 0:
            self.adjust_gain()

    def send_spectrum(self):
        power = np.fft.fftshift(self.power) / (SPECTRUM_EVERY * BLOCK ** 2)
        self.power[:] = 0
        floor = float(np.median(power[::16])) + 1e-20
        signal = float(power[self.channel].mean()) + 1e-20
        self.level = 10 * np.log10(signal * (self.channel.stop - self.channel.start))
        self.snr = 10 * np.log10(signal / floor)
        self.squelched = self.mode == "nfm" and self.squelch > 0 and self.snr < self.squelch

        span = BLOCK // self.zoom
        start = min(max(BLOCK // 2 + self.offset_bins - span // 2, 0), BLOCK - span)
        view = power[start:start + span]
        if span >= WIDTH:
            group = span // WIDTH
            view = view[:group * WIDTH].reshape(WIDTH, group).max(axis=1)
        else:
            view = np.interp(np.linspace(0, span - 1, WIDTH), np.arange(span), view)
        line = np.clip((10 * np.log10(view + 1e-20) + 120) * (255 / 120), 0, 255).astype(np.uint8)
        flags = (FLAG_STEREO if self.demod.stereo else 0) | (FLAG_SQUELCHED if self.squelched else 0)
        gain = 0.0 if self.direct else TUNER_GAINS[self.gain_index]
        header = struct.pack(SPECTRUM_HEADER, self.center + (start - BLOCK // 2) * BIN, span * BIN,
                             self.hz, self.level, self.snr, gain, flags)
        send(b"S", header + line.tobytes())

    def adjust_gain(self):
        """Keep the raw signal in a healthy range: no clipping, but well above the noise."""
        levels, self.raw_level = self.raw_level, []
        if self.fixed_gain or self.direct:
            return
        rms = sum(r for r, _ in levels) / len(levels)
        clipped = sum(c for _, c in levels) / len(levels)
        if (clipped > 0.002 or rms > 32) and self.gain_index > 0:
            self.gain_index = max(0, self.gain_index - 2)
        elif rms < 7 and self.gain_index < len(TUNER_GAINS) - 1:
            self.gain_index += 1
        else:
            return
        self.sdr.set_gain(TUNER_GAINS[self.gain_index])

    def run(self):
        threading.Thread(target=self.read_commands, daemon=True).start()
        command = self.commands.get()
        if command is None:
            return
        self.apply(command)
        threading.Thread(target=self.read_samples, daemon=True).start()
        while True:
            try:
                while True:
                    command = self.commands.get_nowait()
                    if command is None:
                        return
                    self.apply(command)
            except queue.Empty:
                pass
            raw = self.samples.get()
            if isinstance(raw, Exception):
                raise raw
            self.process(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gain", type=float, default=28.0, help="tuner gain in dB to start with")
    parser.add_argument("--fixed-gain", action="store_true", help="never adjust the gain automatically")
    args = parser.parse_args()
    try:
        Engine(args.gain, args.fixed_gain).run()
    except (RuntimeError, BrokenPipeError) as e:
        if isinstance(e, RuntimeError):
            send(b"E", str(e).encode())
        sys.exit(1)


if __name__ == "__main__":
    main()
