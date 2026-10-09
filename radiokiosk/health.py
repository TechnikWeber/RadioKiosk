"""Things that quietly ruin reception: a weak power supply and a hung SDR stick."""

import fcntl
import os
import shutil
import subprocess
from pathlib import Path

from .util import RTL_IDS

USBDEVFS_RESET = 0x5514   # _IO('U', 20)


def undervoltage():
    """Has the Raspberry Pi firmware seen too little voltage since boot? None where that is unknown."""
    if shutil.which("vcgencmd"):
        try:
            out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=3).stdout
            flags = int(out.strip().split("=")[1], 16)
            return bool(flags & 0x10001)   # under-voltage now, or at some point since boot
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            return None
    return None


def reset_sdr():
    """Restart the SDR stick on the USB bus, as if it were replugged.

    The udev rule of rtl-sdr lets ordinary users open the device, and that is
    all a USB reset needs. Returns whether a stick was reset.
    """
    done = False
    for dev in Path("/sys/bus/usb/devices").glob("*/idVendor"):
        try:
            ids = (dev.read_text().strip(), (dev.parent / "idProduct").read_text().strip())
            if ids not in RTL_IDS:
                continue
            bus = int((dev.parent / "busnum").read_text())
            number = int((dev.parent / "devnum").read_text())
            fd = os.open(f"/dev/bus/usb/{bus:03d}/{number:03d}", os.O_WRONLY)
            try:
                fcntl.ioctl(fd, USBDEVFS_RESET, 0)
                done = True
            finally:
                os.close(fd)
        except (OSError, ValueError):
            continue
    return done
