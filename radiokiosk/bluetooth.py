"""Bluetooth through bluetoothctl: connect speakers, and let a phone play through this device.

Sound itself is PipeWire's job: a connected speaker shows up as an audio
output, and a paired phone can stream to this device like to any Bluetooth
speaker.
"""

import asyncio
import re
import shutil
import time

VISIBLE_FOR = 180   # seconds this device stays discoverable for a phone
DEVICE = re.compile(r"Device ([0-9A-F:]{17}) (.*)")


def available():
    return shutil.which("bluetoothctl") is not None


async def ctl(*args, timeout=20):
    proc = await asyncio.create_subprocess_exec(
        "bluetoothctl", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return ""
    return out.decode(errors="replace")


async def _listed(*filter_):
    return dict(DEVICE.findall(await ctl("devices", *filter_)))


class Bluetooth:
    def __init__(self):
        self.pairing = None        # bluetoothctl session that accepts a phone
        self.visible_until = 0
        self.scanning = False

    async def status(self):
        known, paired, connected = await asyncio.gather(_listed(), _listed("Paired"), _listed("Connected"))
        devices = [{"mac": mac, "name": name, "paired": mac in paired, "connected": mac in connected}
                   for mac, name in known.items()]
        # connected first, then paired, unnamed devices (name equals address) last
        devices.sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].replace("-", ":") == d["mac"]))
        return {"devices": devices, "scanning": self.scanning,
                "visible": max(0, round(self.visible_until - time.time()))}

    async def scan(self):
        self.scanning = True
        try:
            await ctl("--timeout", "10", "scan", "on", timeout=15)
        finally:
            self.scanning = False

    async def connect(self, mac):
        if mac not in await _listed("Paired"):
            await ctl("pair", mac, timeout=30)
        await ctl("trust", mac)
        if "Connection successful" not in await ctl("connect", mac, timeout=30):
            raise RuntimeError("could not connect – is the device in pairing mode?")

    async def disconnect(self, mac):
        await ctl("disconnect", mac)

    async def set_visible(self, on):
        """While visible, a phone can find and pair this device without a code."""
        if self.pairing:
            self.pairing.cancel()
            self.pairing = None
        self.visible_until = time.time() + VISIBLE_FOR if on else 0
        if on:
            self.pairing = asyncio.create_task(self._accept())
        else:
            await ctl("discoverable", "off")

    async def _accept(self):
        proc = await asyncio.create_subprocess_exec(
            "bluetoothctl", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)
        say = lambda line: proc.stdin.write(line.encode() + b"\n")
        try:
            for line in ("agent NoInputNoOutput", "default-agent", "pairable on", "discoverable on"):
                say(line)
            end = time.time() + VISIBLE_FOR
            while time.time() < end:
                try:
                    chunk = (await asyncio.wait_for(proc.stdout.read(4096), 1)).decode(errors="replace")
                except asyncio.TimeoutError:
                    continue
                if not chunk:
                    break
                if "(yes/no)" in chunk:
                    say("yes")
                # trust a freshly paired phone so it may open the audio connection
                for mac in re.findall(r"Device ([0-9A-F:]{17}) Paired: yes", chunk):
                    say(f"trust {mac}")
        finally:
            self.visible_until = 0
            try:
                say("discoverable off")
                say("quit")
                await asyncio.wait_for(proc.wait(), 3)
            except (asyncio.TimeoutError, ConnectionError, asyncio.CancelledError):
                proc.kill()
