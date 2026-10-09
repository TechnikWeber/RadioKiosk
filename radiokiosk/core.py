"""Shared state and the rule that only one source is active at a time.

The RTL-SDR can only be opened by one program, so every source asks the core
for ownership before it starts; the core stops whatever ran before.
"""

import asyncio
import re
import shutil
import subprocess
import time
from pathlib import Path

from . import audio, health
from .config import load_json, save_json
from .favorites import Favorites
from .gain import Gains
from .mpv import Mpv
from .sources.adsb import decoder as adsb_decoder
from .util import memory_mb, sdr_present


# errors that mean the stick itself is stuck rather than the reception being poor
SDR_HANG = ("no data from the SDR stick", "stopped delivering data", "does not respond")
MPV_SOURCES = ("webradio", "dab", "fm", "tuner")


def music_dir():
    try:
        out = subprocess.run(["xdg-user-dir", "MUSIC"], capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    return Path(out if out and out != str(Path.home()) else Path.home() / "Music") / "RadioKiosk"


class Core:
    def __init__(self, cfg):
        self.cfg = cfg
        self.clients = set()
        self.sources = {}
        self.active = None
        self.lock = asyncio.Lock()
        self.mpv = Mpv(self._on_mpv)
        self.gains = Gains(cfg)
        self.favorites = Favorites()
        self.receiver_backends = {}   # filled by the service: which backends are installed
        self.state = {
            "source": None, "status": "idle", "title": "", "text": "", "error": None,
            "volume": None, "muted": False, "detail": {}, "sleep_until": None,
            "recording": None, "warnings": [],
        }
        self.last_reset = 0
        self.sleep_task = None
        self.players = {}     # kind -> coroutine function that plays a remembered station
        self.last = load_json("last.json", None)

    def caps(self):
        sdr = sdr_present()
        return {
            "mpv": Mpv.available(),
            "sdr": sdr,
            "dab": shutil.which("welle-cli") is not None,
            "fm": any(self.receiver_backends.values()),
            "adsb": adsb_decoder() is not None,
            "bluetooth": shutil.which("bluetoothctl") is not None,
            "stream": shutil.which("ffmpeg") is not None,
            "apps": [
                {"id": a["id"], "name": a["name"], "needs_sdr": a.get("needs_sdr", False),
                 "available": shutil.which(a["command"][0]) is not None,
                 "too_small": memory_mb() < a.get("min_memory_mb", 0)}
                for a in self.cfg["apps"]
                if not a.get("optional") or shutil.which(a["command"][0])
            ],
        }

    def snapshot(self):
        backends = {name: self.sources[name].backend_id() for name in ("fm", "tuner") if name in self.sources}
        return {**self.state, "caps": self.caps(), "backends": backends}

    def update(self, **changes):
        if all(self.state.get(k) == v for k, v in changes.items()):
            return
        self.state.update(changes)
        asyncio.create_task(self._broadcast())

    async def _broadcast(self):
        snap = self.snapshot()
        for ws in list(self.clients):
            try:
                await ws.send_json(snap)
            except Exception:
                self.clients.discard(ws)

    def broadcast_bytes(self, payload):
        """Spectrum lines for the waterfall; a slow browser must not hold up the others."""
        for ws in list(self.clients):
            asyncio.create_task(self._send_bytes(ws, payload))

    async def _send_bytes(self, ws, payload):
        try:
            await ws.send_bytes(payload)
        except Exception:
            self.clients.discard(ws)

    async def record(self, on):
        """Save what is playing to the music folder, exactly as it arrives."""
        if not on:
            await self._end_recording()
            return
        if self.state["source"] not in MPV_SOURCES or self.state["status"] != "playing":
            raise RuntimeError("nothing is playing")
        folder = music_dir()
        folder.mkdir(parents=True, exist_ok=True)
        title = re.sub(r"[^\w .-]+", "_", self.state["title"]).strip(" ._")[:60] or "radio"
        name = f"{time.strftime('%Y-%m-%d_%H-%M-%S')}_{title}.mkv"
        await self.mpv.command("set_property", "stream-record", str(folder / name))
        self.update(recording=name)

    async def _end_recording(self):
        if self.state["recording"]:
            try:
                await self.mpv.command("set_property", "stream-record", "")
            except Exception:
                pass
            self.update(recording=None)

    async def watch_health(self):
        while True:
            warnings = ["undervoltage"] if health.undervoltage() else []
            self.update(warnings=warnings)
            await asyncio.sleep(60)

    async def take(self, source):
        """Make `source` the active one, stopping the previous owner first."""
        if self.active is not source:
            await self._end_recording()
        if self.active is not None and self.active is not source:
            previous, self.active = self.active, None
            await previous.stop()
            # silence the old station now: if the new one fails to start, it must not keep playing
            try:
                await self.mpv.stop()
            except Exception:
                pass
        self.active = source

    async def stop(self):
        await self._end_recording()
        previous, self.active = self.active, None
        if previous is not None:
            await previous.stop()
        try:
            await self.mpv.stop()
        except Exception:
            pass
        self.update(source=None, status="idle", title="", text="", error=None, detail={})

    def remember(self, kind, title, **what):
        """Note what is playing, so the alarm clock can bring it back."""
        self.last = {"kind": kind, "title": title, **what}
        save_json("last.json", self.last)

    async def play(self, station):
        """Play a station noted by remember()."""
        if not station or station["kind"] not in self.players:
            raise RuntimeError("nothing has been played yet")
        await self.players[station["kind"]](station)

    def sleep_in(self, minutes):
        """Stop whatever plays after `minutes`; 0 cancels the timer."""
        if self.sleep_task:
            self.sleep_task.cancel()
            self.sleep_task = None
        self.update(sleep_until=time.time() + minutes * 60 if minutes else None)
        if minutes:
            self.sleep_task = asyncio.create_task(self._sleep(minutes * 60))

    async def _sleep(self, seconds):
        await asyncio.sleep(seconds)
        self.sleep_task = None
        self.update(sleep_until=None)
        await self.stop()

    def fail(self, message):
        # A hung stick only comes back when it is replugged. A USB reset does the same.
        if any(sign in message for sign in SDR_HANG) and time.time() - self.last_reset > 20:
            self.last_reset = time.time()
            if health.reset_sdr():
                message = "the SDR stick hung and was restarted – please try again"
        self.update(status="error", error=message)

    def _on_mpv(self, msg):
        if self.state["source"] not in (*MPV_SOURCES, "alarm"):
            return
        if msg["event"] == "property-change":
            if msg["name"] == "core-idle" and msg.get("data") is False:
                self.update(status="playing", error=None)
            elif msg["name"] == "media-title" and self.active is not None and self.state["source"] != "alarm":
                self.active.on_title(msg.get("data") or "")
        elif msg["event"] == "end-file" and msg.get("reason") == "error" and self.state["status"] != "error":
            retry = getattr(self.active, "on_playback_error", None)
            if retry and retry():
                return
            self.fail(msg.get("file_error") or "playback failed")

    async def refresh_volume(self):
        try:
            current = next((s for s in await audio.sinks() if s["active"]), None)
        except (RuntimeError, OSError):
            return
        if current:
            self.update(volume=current["volume"], muted=current["muted"])

    async def close(self):
        await self.stop()
        await self.mpv.close()
