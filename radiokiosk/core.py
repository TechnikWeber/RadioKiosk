"""Shared state and the rule that only one source is active at a time.

The RTL-SDR can only be opened by one program, so every source asks the core
for ownership before it starts; the core stops whatever ran before.
"""

import asyncio
import shutil

from . import audio
from .gain import Gains
from .mpv import Mpv
from .util import sdr_present


class Core:
    def __init__(self, cfg):
        self.cfg = cfg
        self.clients = set()
        self.sources = {}
        self.active = None
        self.lock = asyncio.Lock()
        self.mpv = Mpv(self._on_mpv)
        self.gains = Gains(cfg)
        self.state = {
            "source": None, "status": "idle", "title": "", "text": "", "error": None,
            "volume": None, "muted": False, "detail": {},
        }

    def caps(self):
        sdr = sdr_present()
        return {
            "mpv": Mpv.available(),
            "sdr": sdr,
            "dab": shutil.which("welle-cli") is not None,
            "fm": shutil.which("rtl_fm") is not None,
            "apps": [
                {"id": a["id"], "name": a["name"], "needs_sdr": a.get("needs_sdr", False),
                 "available": shutil.which(a["command"][0]) is not None}
                for a in self.cfg["apps"]
                if not a.get("optional") or shutil.which(a["command"][0])
            ],
        }

    def snapshot(self):
        return {**self.state, "caps": self.caps()}

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

    async def take(self, source):
        """Make `source` the active one, stopping the previous owner first."""
        if self.active is not None and self.active is not source:
            previous, self.active = self.active, None
            await previous.stop()
        self.active = source

    async def stop(self):
        previous, self.active = self.active, None
        if previous is not None:
            await previous.stop()
        try:
            await self.mpv.stop()
        except Exception:
            pass
        self.update(source=None, status="idle", title="", text="", error=None, detail={})

    def fail(self, message):
        self.update(status="error", error=message)

    def _on_mpv(self, msg):
        if self.state["source"] not in ("webradio", "dab", "fm", "tuner"):
            return
        if msg["event"] == "property-change":
            if msg["name"] == "core-idle" and msg.get("data") is False:
                self.update(status="playing", error=None)
            elif msg["name"] == "media-title" and self.active is not None:
                self.active.on_title(msg.get("data") or "")
        elif msg["event"] == "end-file" and msg.get("reason") == "error" and self.state["status"] != "error":
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
