"""DAB+ via welle-cli.

welle-cli runs with its built-in web server: /mux.json describes the ensemble
and /mp3/<sid> is an audio stream that mpv plays like any web radio station.
"""

import asyncio

import aiohttp

from ..config import load_json, save_json
from ..util import kill

# Band III blocks used for DAB in Europe
CHANNELS = [f"{n}{c}" for n in range(5, 13) for c in "ABCD"] + [f"13{c}" for c in "ABCDEF"]


class Dab:
    name = "dab"

    def __init__(self, core):
        self.core = core
        self.port = core.cfg["dab_port"]
        self.services = load_json("dab_services.json", [])
        self.proc = None
        self.channel = None
        self.scan_task = None
        self.poll_task = None
        self.scan_state = {"scanning": False, "channel": "", "found": 0}
        self.playing = None
        self.retries = 0

    async def _tune(self, channel):
        await kill(self.proc)
        self.proc = await asyncio.create_subprocess_exec(
            "welle-cli", "-c", channel, "-w", str(self.port),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        self.channel = channel
        for _ in range(50):
            if self.proc.returncode is not None:
                raise RuntimeError("welle-cli could not open the SDR")
            if await self._mux() is not None:
                return
            await asyncio.sleep(0.1)
        raise RuntimeError("welle-cli did not start")

    async def _mux(self):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as http:
                async with http.get(f"http://127.0.0.1:{self.port}/mux.json") as r:
                    return await r.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None

    @staticmethod
    def _audio_services(mux):
        found = []
        for s in mux.get("services", []):
            label = s.get("label", {}).get("label", "").strip()
            is_audio = any(c.get("transportmode") == "audio" for c in s.get("components", []))
            if label and is_audio:
                found.append({"sid": s["sid"], "name": label})
        return found

    async def _scan_channel(self, channel):
        await self._tune(channel)
        services, stable = [], 0
        # no ensemble within 4 s means the block is empty; labels then need a few more seconds
        for tick in range(30):
            await asyncio.sleep(0.5)
            mux = await self._mux() or {}
            current = self._audio_services(mux)
            if not mux.get("services") and tick >= 8:
                break
            stable = stable + 1 if current and len(current) == len(services) else 0
            services = current
            if stable >= 6 and len(services) == len(mux.get("services", [])):
                break
        ensemble = (mux.get("ensemble", {}).get("label", {}).get("label") or "").strip()
        return [{**s, "channel": channel, "ensemble": ensemble} for s in services]

    async def _scan(self):
        found = []
        try:
            for channel in CHANNELS:
                self.scan_state = {"scanning": True, "channel": channel, "found": len(found)}
                self.core.update(source=self.name, status="loading", title="", text="",
                                 detail={"scan": dict(self.scan_state)})
                found += await self._scan_channel(channel)
            self.services = sorted(found, key=lambda s: s["name"].lower())
            save_json("dab_services.json", self.services)
        except RuntimeError as e:
            self.core.fail(str(e))
        finally:
            await kill(self.proc)
            self.scan_state = {"scanning": False, "channel": "", "found": len(found)}
            if self.core.active is self and self.core.state["status"] != "error":
                self.core.active = None
                self.core.update(source=None, status="idle", detail={})

    async def scan(self):
        await self.core.stop()
        async with self.core.lock:
            await self.core.take(self)
            self.scan_task = asyncio.create_task(self._scan())

    async def play(self, sid):
        service = next((s for s in self.services if s["sid"] == sid), None)
        if service is None:
            raise RuntimeError("unknown service")
        async with self.core.lock:
            await self.core.take(self)
            self._cancel_tasks()
            self.core.update(source=self.name, status="loading", title=service["name"],
                             text=service["ensemble"], error=None, detail={"sid": sid})
            try:
                if self.channel != service["channel"] or self.proc is None or self.proc.returncode is not None:
                    await self._tune(service["channel"])
                    await self._wait_for(sid)
                self.playing, self.retries = sid, 0
                self.core.remember("dab", service["name"], sid=sid)
                await self.core.mpv.play(f"http://127.0.0.1:{self.port}/mp3/{sid}")
            except RuntimeError as e:
                self.core.fail(str(e))
                return
            self.poll_task = asyncio.create_task(self._poll_text(sid))

    async def _wait_for(self, sid):
        """After a block change welle-cli answers 404, then 503, until the service is decodable."""
        url = f"http://127.0.0.1:{self.port}/mp3/{sid}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as http:
            for _ in range(60):
                try:
                    async with http.get(url) as r:
                        if r.status == 200:
                            return
                except (aiohttp.ClientError, TimeoutError):
                    pass
                await asyncio.sleep(0.25)
        raise RuntimeError("no reception on block " + self.channel)

    async def _poll_text(self, sid):
        """Show the station's scrolling text (DLS), or a warning while reception is poor."""
        last_errors = 0
        while True:
            await asyncio.sleep(2)
            mux = await self._mux() or {}
            for s in mux.get("services", []):
                if s.get("sid") == sid:
                    errors = s.get("errorcounters", {}).get("frameerrors", 0)
                    text = (s.get("dls", {}).get("label") or "").strip()
                    if errors - last_errors > 20:
                        # audio drops out at this rate; say why instead of showing stale text
                        snr = mux.get("demodulator", {}).get("snr", 0)
                        text = f"weak reception (SNR {snr:.0f} dB)"
                    last_errors = errors
                    if text:
                        self.core.update(text=text)

    def on_title(self, title):
        pass

    def on_playback_error(self):
        """With weak reception the stream starts as garbage; try again a few times."""
        if self.playing is None or self.retries >= 6:
            self.core.fail(f"reception on block {self.channel} is too weak")
            return True
        self.retries += 1
        self.core.update(status="loading")
        asyncio.create_task(self._retry(self.playing))
        return True

    async def _retry(self, sid):
        await asyncio.sleep(2)
        if self.playing == sid and self.core.active is self:
            await self.core.mpv.play(f"http://127.0.0.1:{self.port}/mp3/{sid}")

    def _cancel_tasks(self):
        for task in (self.scan_task, self.poll_task):
            if task and not task.done() and task is not asyncio.current_task():
                task.cancel()
        self.scan_task = self.poll_task = None

    async def stop(self):
        self._cancel_tasks()
        await kill(self.proc)
        self.proc = self.channel = self.playing = None
        self.scan_state["scanning"] = False
