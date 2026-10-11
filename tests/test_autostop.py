"""A radio nobody operates stops by itself after the set hours."""

import asyncio
import unittest
from unittest import mock

from radiokiosk import core as core_module
from radiokiosk.core import Core


class Radio:
    """As much of the core as the watcher looks at."""
    touch, watch_playing = Core.touch, Core.watch_playing

    def __init__(self, hours):
        self.cfg = {"autostop_hours": hours, "autostop_at": None}
        self.state = {"source": "webradio", "title": "Station", "warnings": []}
        self.touched, self.health, self.notices, self.stopped_at = 0, [], set(), None

    def update(self, **changes):
        self.state.update(changes)

    async def stop(self):
        self.stopped_at = self.clock[0]
        self.state.update(source=None, title="")


def run(radio, hours, touch_after=None):
    """Let `hours` pass in the watcher's own steps of 30 seconds."""
    radio.clock = clock = [1_000_000.0]

    async def sleep(seconds):
        clock[0] += seconds
        if touch_after is not None and clock[0] - 1_000_000 >= touch_after * 3600 and not radio.touched_once:
            radio.touched_once = True
            radio.touch()
        if clock[0] - 1_000_000 > hours * 3600:
            raise asyncio.CancelledError

    radio.touched_once = False
    with mock.patch.object(core_module.asyncio, "sleep", sleep), mock.patch.object(core_module.time, "time", lambda: clock[0]):
        try:
            asyncio.run(radio.watch_playing())
        except asyncio.CancelledError:
            pass
    return None if radio.stopped_at is None else round((radio.stopped_at - 1_000_000) / 3600, 1)


class AutoStop(unittest.TestCase):
    def test_stops_after_the_hours_and_says_so(self):
        radio = Radio(8)
        self.assertEqual(run(radio, 10), 8.0)
        self.assertEqual(radio.state["warnings"], ["autostop"])
        radio.touch()
        self.assertEqual(radio.state["warnings"], [])

    def test_a_touch_starts_the_count_again(self):
        self.assertEqual(run(Radio(8), 13, touch_after=6), None)
        self.assertEqual(run(Radio(8), 15, touch_after=6), 14.0)

    def test_never_when_switched_off(self):
        self.assertEqual(run(Radio(0), 100), None)
