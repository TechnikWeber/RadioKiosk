"""Minimal ctypes binding for librtlsdr, just what the receiver engine needs."""

import ctypes
import ctypes.util


def _load():
    for name in filter(None, [ctypes.util.find_library("rtlsdr"), "librtlsdr.so.2", "librtlsdr.so.0"]):
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    raise RuntimeError("librtlsdr is not installed")


def available():
    try:
        _load()
        return True
    except RuntimeError:
        return False


class RtlSdr:
    def __init__(self, sample_rate, index=0):
        self.lib = _load()
        self.dev = ctypes.c_void_p()
        if self.lib.rtlsdr_open(ctypes.byref(self.dev), ctypes.c_uint32(index)) != 0:
            raise RuntimeError("cannot open the SDR stick – is another program using it?")
        self.lib.rtlsdr_set_sample_rate(self.dev, ctypes.c_uint32(sample_rate))
        self.lib.rtlsdr_set_tuner_gain_mode(self.dev, 1)   # manual gain
        self.lib.rtlsdr_set_agc_mode(self.dev, 0)
        self.buffer = None

    def set_frequency(self, hz):
        self.lib.rtlsdr_set_center_freq(self.dev, ctypes.c_uint32(int(hz)))

    def set_gain(self, db):
        self.lib.rtlsdr_set_tuner_gain(self.dev, int(round(db * 10)))

    def set_direct_sampling(self, enabled):
        self.lib.rtlsdr_set_direct_sampling(self.dev, 2 if enabled else 0)

    def reset(self):
        self.lib.rtlsdr_reset_buffer(self.dev)

    def read(self, size):
        """Blocking read of `size` bytes (a multiple of 512) of interleaved 8-bit I/Q."""
        if self.buffer is None or len(self.buffer) != size:
            self.buffer = ctypes.create_string_buffer(size)
        got = ctypes.c_int(0)
        if self.lib.rtlsdr_read_sync(self.dev, self.buffer, size, ctypes.byref(got)) < 0:
            raise RuntimeError("the SDR stick stopped delivering data – replug it")
        return self.buffer.raw[:got.value]
