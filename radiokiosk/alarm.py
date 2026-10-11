"""Alarm clock: at the set time, play a fixed station or whatever was heard last."""

import asyncio
import re
import time

from . import tones
from .config import load_json, save_json

# if the station does not come up (no internet, no reception), wake with a tone instead
FALLBACK_AFTER = 25
FALLBACK_FOR = 120
TONE_FOR = 600        # an alarm set to the tone alone rings this long unless stopped


class Alarm:
    def __init__(self, core):
        self.core = core
        # station: None wakes with the station heard last, otherwise a remembered station
        self.data = {"enabled": False, "time": "07:00", "station": None, **load_json("alarm.json", {})}
        self.fired_on = None

    def set(self, enabled, at, station):
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", at):
            raise ValueError("time must be HH:MM")
        self.data = {"enabled": bool(enabled), "time": at, "station": station}
        self.fired_on = None
        save_json("alarm.json", self.data)

    async def run(self):
        while True:
            await asyncio.sleep(10)
            now = time.localtime()
            today = time.strftime("%Y-%m-%d", now)
            if self.data["enabled"] and time.strftime("%H:%M", now) == self.data["time"] and self.fired_on != today:
                self.fired_on = today
                asyncio.create_task(self.ring())

    async def ring(self):
        only_tone = self.data["station"] == "tone"
        try:
            if only_tone:
                raise RuntimeError("no station wanted")
            await self.core.play(self.data["station"] or self.core.last)
            await asyncio.sleep(FALLBACK_AFTER)
            # idle means somebody already switched the alarm off; only a station
            # that is still loading or failed needs the tone
            if self.core.state["status"] not in ("loading", "error"):
                return
        except RuntimeError:
            pass
        await self.core.stop()
        self.core.update(source="alarm", status="playing", title="Alarm", text="", error=None, detail={})
        await self.core.mpv.play(tones.source(self.core.cfg["tone"], TONE_FOR if only_tone else FALLBACK_FOR))
