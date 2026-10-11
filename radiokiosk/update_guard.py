"""Waits for an updated RadioKiosk to answer and turns the update back if it does not.

Started by the version that was running before the update, from a copy outside
both versions, so it works whatever the new one is like. Standard library only.

    update_guard.py LINK PREVIOUS VERSION URL NOTES
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

WAIT = 150     # seconds the new version has to come up; a Pi 3 needs about twenty
EVERY = 5


def answers(url, version):
    try:
        with urllib.request.urlopen(f"{url}/api/settings", timeout=4) as reply:
            return json.load(reply).get("version") == version
    except (OSError, ValueError):
        return False


def main(link, previous, version, url, notes):
    link, notes = Path(link), Path(notes)
    until = time.time() + WAIT
    while time.time() < until:
        if answers(url, version):
            (notes / "pending").unlink(missing_ok=True)
            return 0
        time.sleep(EVERY)
    fresh = link.with_name(link.name + ".new")
    if fresh.is_symlink() or fresh.exists():
        fresh.unlink()
    fresh.symlink_to(previous)
    os.replace(fresh, link)
    (notes / "failed").write_text(version)
    (notes / "pending").unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "restart", "radiokiosk.service"], check=False)
    return 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:6]))
