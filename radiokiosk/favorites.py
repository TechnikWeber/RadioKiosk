"""Favourites across all sources.

A favourite has the same shape as what Core.remember() notes about the
current station ("kind", "title" and what the source needs to play it), so
Core.play() can start any of them.
"""

from .config import CONFIG_DIR, load_json, save_json


def key(entry):
    """What makes two favourites the same station."""
    kind = entry["kind"]
    if kind == "webradio":
        return kind, entry["station"]["id"]
    if kind == "dab":
        return kind, entry["sid"]
    if kind == "fm":
        return kind, f"{float(entry['mhz']):.2f}"
    if kind == "tuner":
        return kind, f"{int(entry['hz'])}/{entry['mode']}"
    raise ValueError("unknown kind of favourite")


class Favorites:
    def __init__(self):
        self.items = load_json("starred.json", None)
        if self.items is None:
            self.items = self._from_earlier_versions()
            self._save()

    @staticmethod
    def _from_earlier_versions():
        """Favourites used to live in one file per source."""
        items = [{"kind": "webradio", "title": s["name"], "station": s} for s in load_json("favorites.json", [])]
        items += [{"kind": "fm", "title": f"{mhz:.2f} MHz", "mhz": mhz} for mhz in load_json("fm_presets.json", [])]
        items += [{"kind": "tuner", "title": f.get("name") or f"{f['hz'] / 1e6:.4f} MHz", "hz": f["hz"],
                   "mode": f["mode"], "squelch": 0} for f in load_json("tuner_favorites.json", [])]
        for old in ("favorites.json", "fm_presets.json", "tuner_favorites.json"):
            (CONFIG_DIR / old).unlink(missing_ok=True)
        return items

    def _save(self):
        save_json("starred.json", self.items)

    def toggle(self, entry):
        wanted = key(entry)
        kept = [item for item in self.items if key(item) != wanted]
        if len(kept) == len(self.items):
            kept.append(entry)
        self.items = kept
        self._save()
        return self.items

    def clear(self, kind=None):
        self.items = [item for item in self.items if kind and item["kind"] != kind]
        self._save()
        return self.items

    def retitle(self, entry_key, title):
        """A station name learned later (RDS) replaces the bare frequency."""
        for item in self.items:
            if key(item) == entry_key and item["title"] != title:
                item["title"] = title
                self._save()
