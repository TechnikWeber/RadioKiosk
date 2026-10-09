"""Alarm clock: at the set time, play whatever was heard last."""

import asyncio
import re
import time

from .config import load_json, save_json

# if the station does not come up (no internet, no reception), wake with a tone instead
FALLBACK_AFTER = 25
FALLBACK_TONE = "av://lavfi:sine=frequency=880:beep_factor=2:duration=120"


class Alarm:
    def __init__(self, core):
        self.core = core
        self.data = {"enabled": False, "time": "07:00", **load_json("alarm.json", {})}
        self.fired_on = None

    def set(self, enabled, at):
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", at):
            raise ValueError("time must be HH:MM")
        self.data = {"enabled": bool(enabled), "time": at}
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
        try:
            await self.core.replay()
            await asyncio.sleep(FALLBACK_AFTER)
            # idle means somebody already switched the alarm off; only a station
            # that is still loading or failed needs the tone
            if self.core.state["status"] not in ("loading", "error"):
                return
        except RuntimeError:
            pass
        await self.core.stop()
        self.core.update(source="alarm", status="playing", title="Alarm", text="", error=None, detail={})
        await self.core.mpv.play(FALLBACK_TONE)
