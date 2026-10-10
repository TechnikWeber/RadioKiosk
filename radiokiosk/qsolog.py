"""Logbook for contacts (QSOs), also for listeners (SWL), with export as ADIF and CSV.

ADIF is the format every logging program and online logbook reads.
"""

import csv
import io
import re
import subprocess
import time
from pathlib import Path

from .config import load_json, save_json

# band -> a usual frequency in MHz to start from
BANDS = {"160m": 1.85, "80m": 3.65, "60m": 5.36, "40m": 7.1, "30m": 10.12, "20m": 14.2, "17m": 18.12,
         "15m": 21.2, "12m": 24.93, "11m": 27.065, "10m": 28.5, "6m": 50.15, "4m": 70.2, "2m": 145.5,
         "70cm": 433.5, "23cm": 1296.2}
EDGES = {"160m": (1.8, 2.0), "80m": (3.5, 3.8), "60m": (5.35, 5.37), "40m": (7.0, 7.2), "30m": (10.1, 10.15),
         "20m": (14.0, 14.35), "17m": (18.068, 18.168), "15m": (21.0, 21.45), "12m": (24.89, 24.99),
         "11m": (26.5, 27.9), "10m": (28.0, 29.7), "6m": (50.0, 52.0), "4m": (70.0, 70.5), "2m": (144.0, 146.0),
         "70cm": (430.0, 440.0), "23cm": (1240.0, 1300.0)}
MODES = ("SSB", "CW", "FM", "AM", "FT8", "FT4", "RTTY", "PSK", "DIGITALVOICE")
TEXTS = ("call", "name", "qth", "locator", "notes", "worked", "rst_sent", "rst_rcvd")


def band_of(mhz):
    return next((band for band, (low, high) in EDGES.items() if low <= mhz <= high), "")


def documents_dir():
    try:
        out = subprocess.run(["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    return Path(out if out and out != str(Path.home()) else Path.home() / "Documents") / "RadioKiosk"


def clean(entry):
    """An entry as the log keeps it; raises ValueError where the call sign or the frequency make no sense."""
    call = str(entry.get("call", "")).strip().upper()
    if not re.fullmatch(r"[A-Z0-9/]{3,15}", call):
        raise ValueError("a call sign is needed")
    try:
        mhz = round(float(entry.get("mhz") or 0), 4)
    except (TypeError, ValueError):
        raise ValueError("the frequency must be a number in MHz")
    mode = entry.get("mode") if entry.get("mode") in MODES else "SSB"
    band = entry.get("band") if entry.get("band") in BANDS else band_of(mhz)
    record = {key: str(entry.get(key, "")).strip()[:200] for key in TEXTS}
    record.update(call=call, mhz=mhz, mode=mode, band=band, locator=record["locator"].upper(),
                  worked=record["worked"].upper(), time=float(entry.get("time") or time.time()))
    return record


def adif(entries, callsign, swl):
    """The log as an ADIF file."""
    field = lambda name, value: f"<{name}:{len(str(value))}>{value} " if value not in ("", None) else ""
    lines = ["RadioKiosk logbook", field("ADIF_VER", "3.1.4") + field("PROGRAMID", "RadioKiosk") + "<EOH>", ""]
    for e in entries:
        moment = time.gmtime(e["time"])
        lines.append("".join([
            field("CALL", e["call"]), field("QSO_DATE", time.strftime("%Y%m%d", moment)),
            field("TIME_ON", time.strftime("%H%M%S", moment)), field("BAND", e["band"].upper()),
            field("FREQ", f'{e["mhz"]:.4f}' if e["mhz"] else ""), field("MODE", e["mode"]),
            field("RST_SENT", e["rst_sent"]), field("RST_RCVD", e["rst_rcvd"]), field("NAME", e["name"]),
            field("QTH", e["qth"]), field("GRIDSQUARE", e["locator"]),
            # a listener notes whom the station was working
            field("COMMENT", "; ".join(filter(None, [f'worked {e["worked"]}' if e["worked"] else "", e["notes"]]))),
            field("STATION_CALLSIGN", callsign), field("SWL", "Y" if swl else ""), "<EOR>"]))
    return "\n".join(lines) + "\n"


def as_csv(entries):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["date_utc", "time_utc", "call", "band", "mhz", "mode", "rst_sent", "rst_rcvd", "name", "qth",
                     "locator", "worked", "notes"])
    for e in entries:
        moment = time.gmtime(e["time"])
        writer.writerow([time.strftime("%Y-%m-%d", moment), time.strftime("%H:%M", moment), e["call"], e["band"],
                         e["mhz"], e["mode"], e["rst_sent"], e["rst_rcvd"], e["name"], e["qth"], e["locator"],
                         e["worked"], e["notes"]])
    return out.getvalue()


class QsoLog:
    def __init__(self, cfg):
        self.cfg = cfg
        self.entries = load_json("qso_log.json", [])
        self.next_id = max((e["id"] for e in self.entries), default=0) + 1

    def list(self):
        return sorted(self.entries, key=lambda e: -e["time"])

    def save(self, entry):
        record = clean(entry)
        known = next((e for e in self.entries if e["id"] == entry.get("id")), None)
        if known:
            known.update(record)
        else:
            self.entries.append({"id": self.next_id, **record})
            self.next_id += 1
        save_json("qso_log.json", self.entries)

    def delete(self, entry_id):
        self.entries = [e for e in self.entries if e["id"] != entry_id]
        save_json("qso_log.json", self.entries)

    def text(self, kind):
        chronological = sorted(self.entries, key=lambda e: e["time"])
        return as_csv(chronological) if kind == "csv" else adif(chronological, self.cfg["callsign"], self.cfg["swl"])

    def export(self, kind):
        """Write the log into the documents folder and say where it went."""
        kind = "csv" if kind == "csv" else "adi"
        folder = documents_dir()
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"qso-log_{time.strftime('%Y-%m-%d')}.{kind}"
        target.write_text(self.text(kind), encoding="utf-8")
        return str(target)
