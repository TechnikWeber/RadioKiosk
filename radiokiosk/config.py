"""Paths, settings and small JSON helpers."""

import json
import os
from pathlib import Path

APP = "radiokiosk"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / APP
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

DEFAULTS = {
    # 127.0.0.1 keeps the UI local to the kiosk; 0.0.0.0 allows remote control from the LAN.
    "host": "127.0.0.1",
    "port": 8080,
    "country": "DE",
    # [latitude, longitude] of the receiver, for the aircraft map and the weather
    "location": None,
    "location_name": None,   # looked up automatically
    "dab_port": 7979,
    # receiver backend per tile: "engine" (own receiver with waterfall) or "rtl_fm" (classic)
    "fm_backend": "engine",
    "tuner_backend": "engine",
    # FM sound: "auto" picks stereo only on a strong signal, "stereo" and "mono" force it
    "fm_stereo": "auto",
    # "auto" measures a suitable tuner gain per band; a number in dB forces that gain.
    "gain": "auto",
    "apps": [
        # SDR++ gets its own settings folder, so a private SDR++ setup stays untouched.
        {"id": "sdrpp", "name": "SDR++", "needs_sdr": True,
         "command": ["sdrpp", "--autostart", "--root", str(CONFIG_DIR / "sdrpp")]},
        # optional apps only get a tile when they are installed
        {"id": "sdrangel", "name": "SDRangel", "needs_sdr": True, "optional": True,
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
