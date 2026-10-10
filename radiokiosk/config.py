"""Paths, settings and small JSON helpers."""

import json
import os
from pathlib import Path

APP = "radiokiosk"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / APP
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / APP
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

DEFAULTS = {
    # The service listens on the network but only answers this computer unless
    # "remote" is on; then phones and PCs in the local network may control it.
    # Set "host" to 127.0.0.1 to rule that out entirely.
    "host": "0.0.0.0",
    "port": 8080,
    "remote": False,
    "country": "DE",
    # [latitude, longitude] of the receiver, for the aircraft map and the weather
    "location": None,
    "location_name": None,   # looked up automatically
    "dab_port": 7979,
    # screen brightness in percent the idle screen returns to; None until it is first set or dimmed
    "brightness": None,
    # receiver backend per tile: "engine" (own receiver with waterfall), "rtl_fm" (classic),
    # or "auto": the own receiver where the processor is fast enough
    "fm_backend": "auto",
    "tuner_backend": "auto",
    # FM sound: "auto" picks stereo only on a strong signal, "stereo" and "mono" force it
    "fm_stereo": "auto",
    # "auto" measures a suitable tuner gain per band; a number in dB forces that gain.
    "gain": "auto",
    # receivers a phone can play through; each gets a switch where its program is installed
    "receivers": [
        {"id": "airplay", "name": "AirPlay", "command": ["shairport-sync", "-o", "pa", "-a", "RadioKiosk"]},
        {"id": "spotify", "name": "Spotify Connect",
         "command": ["librespot", "--name", "RadioKiosk", "--backend", "pulseaudio"]},
    ],
    "receivers_on": [],
    # slide show, see gallery.py; None until something is set
    "gallery": None,
    # what the idle screen shows: "clock" (black and dimmed), "gallery" or "feed" (the newest article)
    "idle_content": "clock",
    # tiles taken off the start screen, by their id
    "hidden_tiles": [],
    # podcast directory: "fyyd", "apple" or "podcastindex"; only the last needs key and secret
    "podcast_provider": "fyyd",
    "podcast_key": "",
    "podcast_secret": "",
    # logbook: the own call sign, and whether the log is that of a listener (SWL)
    # where the music tile looks; None is the system's music folder
    "music_folder": None,
    # the verse of the day on the idle screen: {"source", "translation", "reference"}, see verses.py
    "verse": None,
    # official weather warnings for the location (Germany only)
    "alerts": True,
    "callsign": "",
    "swl": False,
    "apps": [
        # SDR++ gets its own settings folder, so a private SDR++ setup stays untouched.
        # Next to the kiosk browser it needs more than the 1 GB of a Raspberry Pi 3:
        # there it sent the whole system into swapping for half an hour.
        {"id": "sdrpp", "name": "SDR++", "needs_sdr": True, "min_memory_mb": 1500,
         "command": ["sdrpp", "--autostart", "--root", str(CONFIG_DIR / "sdrpp")]},
        # optional apps only get a tile when they are installed
        {"id": "sdrangel", "name": "SDRangel", "needs_sdr": True, "optional": True, "min_memory_mb": 3000,
         "command": ["sdrangel"]},
    ],
}


def load_json(name, default):
    try:
        return json.loads((CONFIG_DIR / name).read_text())
    except (OSError, ValueError):
        return default


def save_json(name, data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_DIR / (name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(CONFIG_DIR / name)


def save_setting(cfg, key, value):
    """Change one setting from the interface and keep it in config.json."""
    cfg[key] = value
    save_json("config.json", {**load_json("config.json", {}), key: value})


def load_config():
    return {**DEFAULTS, **load_json("config.json", {})}
