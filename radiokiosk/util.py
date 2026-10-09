"""Process and hardware helpers."""

import asyncio
import ctypes
import signal
from pathlib import Path

# USB IDs of RTL2832U based sticks (RTL-SDR Blog V3/V4 and generic ones) and the
# names librtlsdr reports for them
RTL_IDS = {("0bda", "2838"): "Generic RTL2832U OEM", ("0bda", "2832"): "Generic RTL2832U"}


def _read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def sdr_devices():
    """Connected RTL-SDR sticks: librtlsdr name, serial and whether it is a Blog V4."""
    found = []
    for dev in sorted(Path("/sys/bus/usb/devices").glob("*/idVendor")):
        ids = (_read(dev), _read(dev.parent / "idProduct"))
        if ids in RTL_IDS:
            found.append({"name": RTL_IDS[ids], "serial": _read(dev.parent / "serial"),
                          # the V4 tunes shortwave through a built-in upconverter,
                          # older sticks need direct sampling for it
                          "v4": "V4" in _read(dev.parent / "product")})
    return found


def sdr_present():
    return bool(sdr_devices())


async def kill(proc, timeout=3):
    """Terminate a subprocess and wait until it is gone, so the SDR is free again."""
    if proc is None or proc.returncode is not None:
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        # a process blocked on a hung USB device ignores SIGKILL until the kernel
        # gives up; do not let that freeze every other source
        try:
            await asyncio.wait_for(proc.wait(), 1)
        except asyncio.TimeoutError:
            pass


def die_with_parent():
    """For subprocess preexec_fn: have the kernel stop the child when the service dies.

    Otherwise a receiver would outlive a crashed or killed service and keep the SDR stick.
    """
    PR_SET_PDEATHSIG = 1
    ctypes.CDLL(None).prctl(PR_SET_PDEATHSIG, signal.SIGTERM)


async def spawn(*args, **kwargs):
    return await asyncio.create_subprocess_exec(*args, preexec_fn=die_with_parent, **kwargs)
