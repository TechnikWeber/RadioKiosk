"""Output device and volume via pactl (PipeWire or PulseAudio).

Volume is set on the system sink, not inside mpv, so it also applies to
external apps like SDR++.
"""

import asyncio
import json


async def pactl(*args):
    proc = await asyncio.create_subprocess_exec(
        "pactl", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate()
    if proc.returncode:
        raise RuntimeError(err.decode().strip() or "pactl failed")
    return out.decode()


def _kind(name):
    if name.startswith("bluez"):
        return "bluetooth"
    if "usb" in name:
        return "usb"
    if "hdmi" in name:
        return "hdmi"
    return "analog"


async def sinks():
    default = (await pactl("get-default-sink")).strip()
    result = []
    for s in json.loads(await pactl("-f", "json", "list", "sinks")):
        percents = [int(c["value_percent"].rstrip("%")) for c in s.get("volume", {}).values()]
        result.append({
            "name": s["name"],
            "label": s.get("description") or s["name"],
            "kind": _kind(s["name"]),
            "active": s["name"] == default,
            "volume": max(percents, default=0),
            "muted": bool(s.get("mute")),
        })
    return result


async def select(name):
    await pactl("set-default-sink", name)
    # streams that are already playing stay on the old sink unless moved
    for stream in json.loads(await pactl("-f", "json", "list", "sink-inputs")):
        try:
            await pactl("move-sink-input", str(stream["index"]), name)
        except RuntimeError:
            pass


async def set_volume(percent):
    percent = max(0, min(100, int(percent)))
    await pactl("set-sink-mute", "@DEFAULT_SINK@", "0")
    await pactl("set-sink-volume", "@DEFAULT_SINK@", f"{percent}%")


async def watch(callback):
    """Call callback() whenever sinks or the default sink change."""
    while True:
        try:
            proc = await asyncio.create_subprocess_exec(
                "pactl", "subscribe",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            while line := await proc.stdout.readline():
                if b"sink" in line or b"server" in line:
                    await callback()
        except OSError:
            pass
        await asyncio.sleep(5)
