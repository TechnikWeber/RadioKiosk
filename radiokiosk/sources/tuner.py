"""Free listening on any frequency: band plan presets, favourites, manual tuning."""

import json
from pathlib import Path

from ..config import load_json, save_json
from .receiver import Receiver

BANDS = json.loads((Path(__file__).resolve().parent.parent / "bands.json").read_text())


MODES = ("wfm", "nfm", "am", "usb", "lsb")


class Tuner(Receiver):
    name = "tuner"

    def __init__(self, core):
        super().__init__(core)
        self.favorites = load_json("tuner_favorites.json", [])

    async def tune(self, hz, mode, squelch=0, zoom=1, label=""):
        hz = int(min(1.75e9, max(100e3, float(hz))))
        if mode not in MODES:
            raise RuntimeError("unknown mode")
        # signal levels differ a lot between bands, so the gain is remembered per 2 MHz slice
        gain_key = f"{hz // 2_000_000 * 2}MHz"
        async with self.core.lock:
            await self._receive(hz, mode, gain_key, label or self.format(hz),
                                {"hz": hz, "mode": mode, "squelch": squelch, "zoom": zoom}, squelch, zoom)

    @staticmethod
    def format(hz):
        return f"{hz / 1e3:,.1f} kHz".replace(",", " ") if hz < 30e6 else f"{hz / 1e6:.4f} MHz"

    def toggle_favorite(self, entry):
        key = (int(entry["hz"]), entry["mode"])
        if any((f["hz"], f["mode"]) == key for f in self.favorites):
            self.favorites = [f for f in self.favorites if (f["hz"], f["mode"]) != key]
        else:
            self.favorites.append({"hz": key[0], "mode": key[1], "name": entry.get("name", "")})
            self.favorites.sort(key=lambda f: f["hz"])
        save_json("tuner_favorites.json", self.favorites)
        return self.favorites
