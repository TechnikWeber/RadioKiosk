"""The computer itself: screen brightness, power, Wi-Fi and updates.

Everything here is optional; the interface only offers what this computer
actually supports.
"""

import asyncio
import os
import shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


async def run(*args, timeout=30):
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 1, ""
    return proc.returncode, out.decode(errors="replace").strip()


# --- brightness -----------------------------------------------------------

def _backlight():
    """A backlight this user may set, e.g. the official Raspberry Pi display."""
    for device in sorted(Path("/sys/class/backlight").glob("*")):
        if os.access(device / "brightness", os.W_OK):
            return device
    return None


def brightness():
    device = _backlight()
    if device is None:
        return None
    try:
        return round(int((device / "brightness").read_text()) * 100 / int((device / "max_brightness").read_text()))
    except (OSError, ValueError, ZeroDivisionError):
        return None


def set_brightness(percent):
    device = _backlight()
    if device is None:
        raise RuntimeError("this screen's brightness cannot be set")
    percent = max(5, min(100, int(percent)))   # never fully dark: the screen is the only way back
    maximum = int((device / "max_brightness").read_text())
    (device / "brightness").write_text(str(max(1, round(maximum * percent / 100))))
    return percent


# --- power ----------------------------------------------------------------

async def can_power_off():
    """May this service switch the computer off without a password?"""
    if not shutil.which("busctl"):
        return False
    code, out = await run("busctl", "call", "org.freedesktop.login1", "/org/freedesktop/login1",
                          "org.freedesktop.login1.Manager", "CanPowerOff", timeout=5)
    return code == 0 and '"yes"' in out


async def power(action):
    if action not in ("poweroff", "reboot"):
        raise RuntimeError("unknown action")
    code, out = await run("systemctl", action)
    if code:
        raise RuntimeError(out or "the system refused")


# --- Wi-Fi ----------------------------------------------------------------

def has_wifi():
    return shutil.which("nmcli") is not None


async def wifi_networks():
    code, out = await run("nmcli", "-t", "-f", "IN-USE,SIGNAL,SECURITY,SSID", "dev", "wifi", "list", timeout=20)
    networks = {}
    for line in out.splitlines() if code == 0 else []:
        used, signal, security, name = line.replace("\\:", "\0").split(":", 3)
        name = name.replace("\0", ":")
        if name and (name not in networks or used == "*"):
            networks[name] = {"name": name, "signal": int(signal or 0), "secured": bool(security.strip()),
                              "connected": used == "*"}
    return sorted(networks.values(), key=lambda n: (not n["connected"], -n["signal"]))


async def wifi_connect(name, password=""):
    args = ["nmcli", "dev", "wifi", "connect", name]
    if password:
        args += ["password", password]
    code, out = await run(*args, timeout=45)
    if code:
        raise RuntimeError("could not connect to this network – wrong password?")


async def _wifi_connection():
    """Name of the Wi-Fi connection in use."""
    code, out = await run("nmcli", "-t", "-f", "TYPE,NAME", "connection", "show", "--active", timeout=10)
    for line in out.splitlines() if code == 0 else []:
        kind, name = line.split(":", 1)
        if kind == "802-11-wireless":
            return name.replace("\\:", ":")
    return None


async def wifi_powersave():
    """Is the Wi-Fi adapter saving power? None without a Wi-Fi connection.

    Power saving lets some adapters miss traffic for minutes, the one in a
    Raspberry Pi 3 among them: streams stall and the computer drops off the network.
    """
    if not has_wifi() or (name := await _wifi_connection()) is None:
        return None
    code, out = await run("nmcli", "-g", "802-11-wireless.powersave", "connection", "show", name, timeout=10)
    return None if code else out.strip() not in ("disable", "2")


async def set_wifi_powersave(on):
    name = await _wifi_connection()
    if name is None:
        raise RuntimeError("no Wi-Fi connection")
    code, _ = await run("nmcli", "connection", "modify", name, "802-11-wireless.powersave", "3" if on else "2")
    if code:
        raise RuntimeError("this computer does not let RadioKiosk change that setting")
    # the adapter takes the setting when it connects; the interface is back within seconds
    await run("nmcli", "connection", "up", name, timeout=45)


# --- update ---------------------------------------------------------------

def can_update():
    """Only an installation made by the installer (a git checkout run as a service) updates itself."""
    # INVOCATION_ID is set by systemd: a copy started by hand for development is left alone
    return (PROJECT_DIR / ".git").exists() and shutil.which("git") is not None and "INVOCATION_ID" in os.environ


async def update():
    code, out = await run("git", "-C", str(PROJECT_DIR), "pull", "--ff-only", timeout=120)
    if code:
        raise RuntimeError("update failed – is there an internet connection?")
    changed = "Already up to date" not in out and "Bereits aktuell" not in out
    if changed:
        # restart in a moment, so this request can still be answered
        await asyncio.create_subprocess_exec(
            # without the accuracy a timer may fire up to a minute late
            "systemd-run", "--user", "--on-active=2", "--timer-property=AccuracySec=100ms", "systemctl", "--user", "restart", "radiokiosk.service",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    return changed
