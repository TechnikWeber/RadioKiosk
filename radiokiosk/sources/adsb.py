"""Aircraft positions (ADS-B on 1090 MHz) through a dump1090-compatible decoder.

The decoder runs with networking enabled; its BaseStation port delivers one
CSV line per decoded message, which every dump1090 flavour and readsb support.
"""

import asyncio
import shutil
import time

from ..util import kill, spawn

DECODERS = ("readsb", "dump1090-fa", "dump1090-mutability", "dump1090")
SBS_PORT = 30003
FORGET_AFTER = 60   # seconds without a message


def decoder():
    return next((name for name in DECODERS if shutil.which(name)), None)


class Adsb:
    name = "adsb"

    def __init__(self, core):
        self.core = core
        self.proc = None
        self.reader = None
        self.connection = None
        self.aircraft = {}

    async def start(self):
        binary = decoder()
        if binary is None:
            raise RuntimeError("no ADS-B decoder installed")
        await self.core.stop()
        async with self.core.lock:
            await self.core.take(self)
            self.aircraft = {}
            args = [binary, "--net", "--net-sbs-port", str(SBS_PORT)]
            if binary == "readsb":
                args += ["--device-type", "rtlsdr"]   # readsb only opens a stick when told which kind
            help_text = await self._help(binary)
            if "--net-http-port" in help_text:
                # the classic dump1090 serves its own map on 8080 by default, which is our port
                args += ["--net-http-port", str(SBS_PORT + 1)]
            if "--quiet" in help_text:
                args += ["--quiet"]
            self.core.update(source=self.name, status="loading", title="ADS-B", text="", error=None, detail={})
            self.reader = asyncio.create_task(self._run(args))

    @staticmethod
    async def _help(binary):
        proc = await asyncio.create_subprocess_exec(
            binary, "--help", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await proc.communicate()
        return out.decode(errors="replace")

    async def _run(self, args):
        # right after another receiver let go of the stick, opening it can fail once
        for attempt in range(3):
            proc = self.proc = await spawn(
                *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            # keep the writer too: dropping it would close the connection
            stream, self.connection = await self._connect(proc)
            if stream is not None:
                break
            await kill(proc)
            await asyncio.sleep(1)
        else:
            self.core.fail("the ADS-B decoder could not open the SDR stick")
            return
        self.core.update(status="playing")
        while line := await stream.readline():
            self._parse(line.decode(errors="replace").strip().split(","))
        if proc is self.proc:
            self.core.fail("the ADS-B decoder stopped unexpectedly")

    @staticmethod
    async def _connect(proc):
        for _ in range(20):
            if proc.returncode is not None:
                break
            try:
                return await asyncio.open_connection("127.0.0.1", SBS_PORT)
            except OSError:
                await asyncio.sleep(0.25)
        return None, None

    def _parse(self, f):
        """One BaseStation line: MSG,type,,,hex,,,,,,callsign,altitude,speed,track,lat,lon,..."""
        if len(f) < 16 or f[0] != "MSG" or not f[4]:
            return
        plane = self.aircraft.setdefault(f[4], {"hex": f[4]})
        plane["seen"] = time.time()
        for key, index, convert in (("flight", 10, str.strip), ("altitude", 11, float), ("speed", 12, float),
                                    ("track", 13, float), ("lat", 14, float), ("lon", 15, float)):
            if f[index].strip():
                try:
                    plane[key] = convert(f[index])
                except ValueError:
                    pass

    def list(self):
        limit = time.time() - FORGET_AFTER
        self.aircraft = {k: p for k, p in self.aircraft.items() if p["seen"] >= limit}
        return [{**p, "seen": round(time.time() - p["seen"])} for p in self.aircraft.values()]

    def on_title(self, title):
        pass

    async def stop(self):
        if self.reader:
            self.reader.cancel()
        proc, self.proc = self.proc, None
        await kill(proc)
