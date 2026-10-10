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


# What librtlsdr calls the tuner chips, and from where to where each of them tunes (MHz).
# The R820T family is in nearly every stick sold today; the others are in older DVB-T sticks.
TUNERS = {1: ("E4000", 52, 2200), 2: ("FC0012", 22, 948), 3: ("FC0013", 22, 1100), 4: ("FC2580", 146, 924),
          5: ("R820T", 24, 1766), 6: ("R828D", 24, 1766)}


def devices():
    """Every stick librtlsdr would open, by its own account: name, maker, product, serial.

    Unlike a table of USB IDs this knows all sticks the installed library supports,
    and it does not open them, so it works while one is in use.
    """
    lib = _load()
    found = []
    for index in range(lib.rtlsdr_get_device_count()):
        maker, product, serial = (ctypes.create_string_buffer(256) for _ in range(3))
        lib.rtlsdr_get_device_usb_strings(ctypes.c_uint32(index), maker, product, serial)
        lib.rtlsdr_get_device_name.restype = ctypes.c_char_p
        found.append({"name": (lib.rtlsdr_get_device_name(ctypes.c_uint32(index)) or b"").decode(errors="replace"),
                      "maker": maker.value.decode(errors="replace"), "product": product.value.decode(errors="replace"),
                      "serial": serial.value.decode(errors="replace")})
    return found


def tuner(index=0):
    """(name, lowest, highest MHz) of a stick's tuner; None when the stick cannot be opened right now."""
    lib = _load()
    dev = ctypes.c_void_p()
    if lib.rtlsdr_open(ctypes.byref(dev), ctypes.c_uint32(index)) != 0:
        return None
    try:
        return TUNERS.get(lib.rtlsdr_get_tuner_type(dev))
    finally:
        lib.rtlsdr_close(dev)


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
