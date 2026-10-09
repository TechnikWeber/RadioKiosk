"""External full-screen programs (e.g. SDR++) that take over SDR and screen."""

import asyncio
import json

from ..config import CONFIG_DIR
from ..gain import TUNER_GAINS
from ..util import kill, sdr_devices, spawn


def seed_sdrpp(gain_db):
    """First start only: preselect the stick, a sane gain and an FM frequency.

    A fresh SDR++ has no source selected and gain 0, so it stays silent until
    the user finds both settings. SDR++ fills in every key missing here.
    """
    root = CONFIG_DIR / "sdrpp"
    if (root / "config.json").exists():
        return
    root.mkdir(parents=True, exist_ok=True)
    gain = min(range(len(TUNER_GAINS)), key=lambda i: abs(TUNER_GAINS[i] - gain_db))
    # SDR++ stores the index into the tuner's gain steps, not the dB value
    devices = {f"[{d['serial']}] {d['name']}##{i}": {"gain": gain, "tunerAgc": False, "rtlAgc": False,
                                                     "sampleRate": 2400000.0}
               for i, d in enumerate(sdr_devices())}
    (root / "rtl_sdr_config.json").write_text(json.dumps({"device": "", "devices": devices}, indent=2))
    (root / "config.json").write_text(json.dumps({"source": "RTL-SDR", "frequency": 100000000.0}, indent=2))


class Apps:
    name = "app"

    def __init__(self, core):
        self.core = core
        self.proc = None

    async def start(self, app_id):
        app = next((a for a in self.core.cfg["apps"] if a["id"] == app_id), None)
        if app is None:
            raise RuntimeError("unknown app")
        await self.core.stop()
        if app_id == "sdrpp":
            seed_sdrpp(self.core.gains.known("fm", 29.7))
        async with self.core.lock:
            await self.core.take(self)
            self.proc = await spawn(
                *app["command"], stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            self.core.update(source=self.name, status="playing", title=app["name"], text="",
                             error=None, detail={"app": app_id})
            asyncio.create_task(self._watch(self.proc))

    async def _watch(self, proc):
        await proc.wait()
        if self.core.active is self and self.proc is proc:
            await self.core.stop()

    def on_title(self, title):
        pass

    async def stop(self):
        proc, self.proc = self.proc, None
        await kill(proc)
