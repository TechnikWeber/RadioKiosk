"""A Bible verse for the day, for the idle screen: from a curated list or the Herrnhuter Losungen.

Both come from the Bible Verse Widget (github.com/TechnikWeber/bible-verse-widget).
The verse of a day is picked exactly as there, so desktop and radio agree.

The Losungen are published by the Evangelische Brüder-Unität. They are free of
charge for non-commercial use but not free content, so they are never part of
this program: the user downloads the year file from losungen.de, where the
terms are accepted, and imports it here. A file the widget has already
imported on this computer is used as it is.
"""

import datetime
import io
import json
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .config import CONFIG_DIR, WEB_DIR

VERSES = WEB_DIR.parent / "verses"
LANGUAGES = ("de", "en", "es")
DEFAULTS = {"source": "list", "translation": "auto", "reference": True}
MODULUS, MULTIPLIER, YEAR_SALT = 2147483647, 48271, 2654435761
# the published XML has gone through several spellings of its tags
FIELDS = {"date": ("Datum", "date"), "sunday": ("Sonntag", "Sonntagsname"),
          "losung_text": ("Losungstext", "Losungtext"), "losung_ref": ("Losungsvers", "Losungvers"),
          "lehrtext_text": ("Lehrtext", "Lehrtexttext"), "lehrtext_ref": ("Lehrtextvers",)}


def year_permutation(year, count):
    """The verse list shuffled for one year, the same on every device (Lehmer generator, Fisher-Yates)."""
    state = (year * YEAR_SALT) % MODULUS
    if state <= 0:
        state += MODULUS - 1
    order = list(range(count))
    for i in range(count - 1, 0, -1):
        state = (state * MULTIPLIER) % MODULUS
        j = state % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def verse_index(day, count):
    """Which verse of the list belongs to a date: no repeats within a year, no stored state."""
    if count <= 0:
        return 0
    return year_permutation(day.year, count)[(day.timetuple().tm_yday - 1) % count]


def _clean(text):
    return " ".join(unicodedata.normalize("NFC", text or "").split())


def parse_losungen(payload):
    """The days of a Losungen year file (the XML, or the ZIP it comes in)."""
    if payload[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".xml")]
            if not names:
                raise ValueError("there is no XML file in this archive")
            payload = archive.read(names[0])
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        raise ValueError("this is not a Losungen year file")
    days = []
    for element in root.iter():
        fields = {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in element}
        value = lambda key: _clean(next((fields[name] for name in FIELDS[key] if name in fields), ""))
        date = re.match(r"(\d{4})-(\d{2})-(\d{2})", value("date"))
        if not date or not value("losung_text") or not value("lehrtext_text"):
            continue
        days.append({"date": "-".join(date.groups()), "sunday": value("sunday"),
                     "losung": {"text": value("losung_text"), "ref": value("losung_ref")},
                     "lehrtext": {"text": value("lehrtext_text"), "ref": value("lehrtext_ref")}})
    if not days:
        raise ValueError("this is not a Losungen year file")
    return sorted(days, key=lambda d: d["date"])


def losungen_places():
    """Where a year's file may lie: RadioKiosk's own folder first, then the widget's."""
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return [CONFIG_DIR, data_home / "bible-verse-widget"]


class Verses:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lists = {}
        self.losungen = {}   # year -> {date: day}

    @property
    def settings(self):
        return {**DEFAULTS, **(self.cfg.get("verse") or {})}

    def check(self, key, value):
        if key == "source" and value in ("list", "losungen"):
            return value
        if key == "translation" and value in ("auto", *LANGUAGES):
            return value
        if key == "reference" and isinstance(value, bool):
            return value
        raise ValueError("unknown setting")

    def _list(self, language):
        if language not in self.lists:
            self.lists[language] = json.loads((VERSES / f"{language}.json").read_text(encoding="utf-8"))
        return self.lists[language]

    def _year(self, year):
        if year not in self.losungen:
            for place in losungen_places():
                try:
                    days = json.loads((place / f"losungen-{year}.json").read_text(encoding="utf-8"))["days"]
                    self.losungen[year] = {d["date"]: d for d in days}
                    break
                except (OSError, ValueError, KeyError, TypeError):
                    continue
        return self.losungen.get(year)

    def years(self):
        """The years Losungen are there for."""
        found = set()
        for place in losungen_places():
            found.update(int(m[1]) for p in place.glob("losungen-*.json") if (m := re.fullmatch(r"losungen-(\d{4})", p.stem)))
        return sorted(found)

    def keep(self, payload):
        """Import a downloaded year file; returns the years it brought."""
        days = parse_losungen(payload)
        years = sorted({d["date"][:4] for d in days})
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        for year in years:
            of_year = [d for d in days if d["date"].startswith(year)]
            (CONFIG_DIR / f"losungen-{year}.json").write_text(json.dumps({
                "source": "Herrnhuter Losungen", "year": int(year),
                "copyright": "© Evangelische Brüder-Unität – Herrnhuter Brüdergemeine", "url": "https://www.losungen.de/",
                "note": "Non-commercial use only. Not redistributable with this program.",
                "count": len(of_year), "days": of_year}, ensure_ascii=False, indent=1), encoding="utf-8")
            self.losungen.pop(int(year), None)
        return [int(y) for y in years]

    def keep_from(self, folder):
        """Import every Losungen file lying in a folder, such as a USB stick or the download folder."""
        found = []
        for path in sorted(Path(folder).expanduser().iterdir()):
            if path.is_file() and path.suffix.lower() in (".zip", ".xml") and "losung" in path.name.lower():
                try:
                    found += self.keep(path.read_bytes())
                except (ValueError, OSError, zipfile.BadZipFile):
                    continue
        if not found:
            raise RuntimeError("no Losungen file found in this folder")
        return sorted(set(found))

    def today(self, interface_language, day=None):
        """What the idle screen shows today, in the settings' source and translation."""
        day = day or datetime.date.today()
        settings = self.settings
        language = settings["translation"] if settings["translation"] != "auto" else interface_language
        language = language if language in LANGUAGES else "en"
        result = {**settings, "years": self.years(), "missing": False, "date": day.isoformat()}
        if settings["source"] == "losungen":
            entry = (self._year(day.year) or {}).get(day.isoformat())
            if entry:
                return {**result, "used": "losungen", "sunday": entry.get("sunday", ""),
                        "texts": [entry["losung"], entry["lehrtext"]],
                        "credit": "Herrnhuter Losungen · © Evangelische Brüder-Unität"}
            result["missing"] = True   # no file for this year: the list stands in
        verses = self._list(language)
        verse = verses["verses"][verse_index(day, len(verses["verses"]))]
        return {**result, "used": "list", "sunday": "", "texts": [{"text": verse["text"], "ref": verse["ref"]}],
                "credit": verses["translation"]["name"]}
