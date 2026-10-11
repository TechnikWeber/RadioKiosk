"""The sounds of alarm, timer and reminders, made by mpv's own tone generator: no sound files needed.

Each is a formula over the time t in seconds. A sound that is to wake somebody
without getting on the nerves has silence in it, so all of these are short
strokes with a pause, not a steady tone.
"""

import asyncio
import shutil

from .util import spawn

# name -> formula; exp(-k*mod(t,p)) is a stroke every p seconds that dies away at rate k
TONES = {
    "tick": "0.8*sin(2*PI*1400*t)*exp(-90*mod(t,0.5))",
    "knock": "0.9*sin(2*PI*420*t)*exp(-35*mod(t,0.8))",
    "bell": "(0.45*sin(2*PI*660*t)+0.3*sin(2*PI*1320*t)+0.15*sin(2*PI*1980*t))*exp(-4*mod(t,1.6))",
    "beeps": "0.5*sin(2*PI*2000*t)*lt(mod(t,1),0.55)*lt(mod(t,0.14),0.07)",
}
DEFAULT = "tick"


def source(name, seconds):
    """What to hand mpv to hear tone `name` for so many seconds."""
    formula = TONES.get(name, TONES[DEFAULT])
    return f"av://lavfi:aevalsrc=exprs='{formula}':s=44100:d={seconds}"


async def play(name, seconds):
    """Play a tone over whatever is playing, with a player of its own; None where mpv is missing."""
    if not shutil.which("mpv"):
        return None
    try:
        return await spawn("mpv", "--no-video", "--no-terminal", "--no-config", source(name, seconds),
                           stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    except OSError:
        return None


SIDES = {"left": "{0}|0", "right": "0|{0}", "both": "{0}|{0}"}
TEST = "0.5*sin(2*PI*440*t)*lt(mod(t,0.5),0.32)"   # four short strokes of a plain 440 Hz
TEST_FOR = 2


async def test(side):
    """A short tone from the left loudspeaker, the right one or both, to check the wiring of the output."""
    if side not in SIDES:
        raise ValueError("unknown setting")
    if not shutil.which("mpv"):
        raise RuntimeError("mpv is not installed")
    channels = SIDES[side].format(TEST)
    return await spawn("mpv", "--no-video", "--no-terminal", "--no-config",
                       f"av://lavfi:aevalsrc=exprs='{channels}':c=stereo:s=44100:d={TEST_FOR}",
                       stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
