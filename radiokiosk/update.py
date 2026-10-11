"""Updates from the releases on GitHub.

A device in the field has nobody to log in and repair it, so an update must
never leave it dark. A new version is therefore fetched into a folder of its
own next to the running one and tried out there before anything changes. Only
then a link is turned to it and the service restarted. A guard started
beforehand waits for the new version to answer; if it does not, the guard turns
the link back and the old version runs again.

Layout, with the installer's folder as `radiokiosk`:
    radiokiosk/            the git checkout the installer made
    radiokiosk-versions/   one folder per release fetched since, and the notes of the update in progress
    radiokiosk-current     link to the folder the service runs from
"""

import asyncio
import json
import os
import random
import re
import shutil
import sys
import time
from pathlib import Path

import aiohttp

from . import __version__
from .device import PROJECT_DIR, run

RELEASES = "https://api.github.com/repos/{repo}/releases?per_page=20"
CHECK_EVERY = 24 * 3600
NIGHT = (3, 5)                 # local hours in which an automatic update may run
UNIT = Path.home() / ".config/systemd/user/radiokiosk.service"
ENTRIES = (Path.home() / ".local/share/applications/radiokiosk.desktop", Path.home() / ".config/autostart/radiokiosk.desktop")
GUARD = Path(__file__).with_name("update_guard.py")


def numbers(tag):
    """v0.19.0 as (0, 19, 0); None for a tag that is not a version."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag or "")
    return tuple(int(n) for n in match.groups()) if match else None


def newest(releases):
    """The release with the highest version; drafts and tags that are no versions do not count."""
    found = [r for r in releases if isinstance(r, dict) and not r.get("draft") and numbers(r.get("tag_name"))]
    return max(found, key=lambda r: numbers(r["tag_name"]), default=None)


def repo_of(url):
    """owner/name from a GitHub address as git stores it, None for any other host."""
    match = re.search(r"github\.com[:/]+([^/]+/[^/]+?)(?:\.git)?/?$", url.strip())
    return match.group(1) if match else None


def turn(link, target):
    """Point `link` at `target` in one step, so there is no moment without it."""
    fresh = link.with_name(link.name + ".new")
    if fresh.is_symlink() or fresh.exists():
        fresh.unlink()
    fresh.symlink_to(target)
    os.replace(fresh, link)


class Updater:
    def __init__(self, core, cfg):
        self.core, self.cfg = core, cfg
        self.available = None     # {"version", "tag", "notes", "url"} of a release newer than this one
        self.checked = 0
        self.failed = None        # version of an update that was turned back
        self.busy = False
        self.places = None        # (checkout, versions folder, link), found once

    def installed(self):
        """Only what the installer set up updates itself: a git checkout run as the service."""
        # INVOCATION_ID is set by systemd: a copy started by hand for development is left alone
        return (PROJECT_DIR / ".git").exists() and shutil.which("git") is not None \
            and "INVOCATION_ID" in os.environ and UNIT.exists()

    async def find_places(self):
        if self.places is None:
            code, out = await run("git", "-C", str(PROJECT_DIR), "rev-parse", "--path-format=absolute", "--git-common-dir")
            if code or not out:
                raise RuntimeError("update failed: this is not an installed copy")
            checkout = Path(out.splitlines()[-1]).parent
            self.places = (checkout, checkout.with_name(checkout.name + "-versions"),
                           checkout.with_name(checkout.name + "-current"))
        return self.places

    def info(self):
        return {"available": self.available, "failed": self.failed, "checked": self.checked,
                "auto": bool(self.cfg["auto_update"]), "can": self.installed(), "busy": self.busy}

    # --- start -----------------------------------------------------------

    async def started(self):
        """After a restart: note how the last update ended and clear away versions no longer needed."""
        if not self.installed():
            return
        try:
            checkout, versions, link = await self.find_places()
            failed, previous = versions / "failed", versions / "previous"
            if failed.exists():
                self.failed = failed.read_text().strip() or None
            if not versions.is_dir():
                return
            keep = {PROJECT_DIR.resolve(), checkout.resolve()}
            if previous.exists():
                keep.add(Path(previous.read_text().strip()).resolve())
            if (versions / "pending").exists():
                return                      # the guard has not decided yet: touch nothing
            for folder in versions.iterdir():
                if folder.is_dir() and folder.resolve() not in keep:
                    await run("git", "-C", str(checkout), "worktree", "remove", "--force", str(folder))
            await run("git", "-C", str(checkout), "worktree", "prune")
        except (OSError, RuntimeError):
            pass                            # tidying up is never worth a failed start

    # --- looking for a release ----------------------------------------

    async def check(self):
        """Ask GitHub for the releases; raises RuntimeError when that is not possible."""
        code, url = await run("git", "-C", str(PROJECT_DIR), "remote", "get-url", "origin")
        repo = repo_of(url) if not code else None
        if not repo:
            raise RuntimeError("update failed: where this copy comes from is unknown")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as http:
                async with http.get(RELEASES.format(repo=repo), headers={"Accept": "application/vnd.github+json"}) as r:
                    if r.status != 200:
                        raise RuntimeError("update failed: GitHub does not answer right now")
                    releases = await r.json()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            raise RuntimeError("update failed – is there an internet connection?")
        self.checked = time.time()
        release = newest(releases if isinstance(releases, list) else [])
        if release and numbers(release["tag_name"]) > (numbers(__version__) or (0, 0, 0)):
            self.available = {"version": release["tag_name"].lstrip("v"), "tag": release["tag_name"],
                              "notes": (release.get("body") or "").strip()[:4000], "url": release.get("html_url", "")}
            if self.failed != self.available["version"]:
                self.core.update(update=self.available["version"])
        else:
            self.available = None
            self.core.update(update=None)
        return self.available

    # --- installing one ---------------------------------------------------

    async def apply(self, tag=None):
        """Fetch the available release, try it, switch to it and restart. True if a restart follows.

        With `tag` it is that release instead, whether older or newer: the way back by hand."""
        if not self.installed():
            raise RuntimeError("update failed: this is not an installed copy")
        if self.busy:
            raise RuntimeError("update failed: an update is already running")
        if tag and not numbers(tag):
            raise RuntimeError("update failed: this is not a version")
        release = {"version": tag.lstrip("v"), "tag": tag} if tag else self.available
        if not release:
            return False
        self.busy = True
        try:
            await self._apply(release)
        finally:
            self.busy = False
        return True

    async def _apply(self, release):
        checkout, versions, link = await self.find_places()
        tag, target = release["tag"], versions / release["tag"]
        git = ("git", "-C", str(checkout))
        _, shallow = await run(*git, "rev-parse", "--is-shallow-repository")
        depth = ("--depth", "1") if shallow.strip() == "true" else ()
        code, _ = await run(*git, "fetch", *depth, "--force", "origin", "tag", tag, timeout=300)
        if code:
            raise RuntimeError("update failed – is there an internet connection?")
        versions.mkdir(parents=True, exist_ok=True)
        if target.exists():   # left from an attempt that was turned back
            await run(*git, "worktree", "remove", "--force", str(target))
            shutil.rmtree(target, ignore_errors=True)
            await run(*git, "worktree", "prune")
        code, out = await run(*git, "worktree", "add", "--detach", str(target), tag, timeout=120)
        if code:
            raise RuntimeError("update failed: the new version could not be unpacked")
        # the new version must at least load here: a missing package shows now, not after the switch
        probe = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "import radiokiosk.__main__", cwd=str(target),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, errors = await asyncio.wait_for(probe.communicate(), 180)
        except asyncio.TimeoutError:
            probe.kill()
            errors = b"timeout"
        if probe.returncode:
            missing = re.search(r"No module named '([^']+)'", errors.decode(errors="replace"))
            await run(*git, "worktree", "remove", "--force", str(target))
            raise RuntimeError(f"update failed: the new version needs the package {missing.group(1)}, run the installer again"
                               if missing else "update failed: the new version does not start on this computer")

        guard = versions / "update_guard.py"
        shutil.copyfile(GUARD, guard)          # the guard of the version known to work
        (versions / "previous").write_text(str(PROJECT_DIR))
        (versions / "pending").write_text(release["version"])
        (versions / "failed").unlink(missing_ok=True)
        self._point_service_at(checkout, link)
        turn(link, target)
        await run("systemctl", "--user", "daemon-reload")
        url = f"http://127.0.0.1:{self.cfg['port']}"
        quiet = {"stdout": asyncio.subprocess.DEVNULL, "stderr": asyncio.subprocess.DEVNULL}
        await asyncio.create_subprocess_exec(
            "systemd-run", "--user", "--on-active=15", "--collect", sys.executable, str(guard),
            str(link), str(PROJECT_DIR), release["version"], url, str(versions), **quiet)
        # restart in a moment, so this request can still be answered
        await asyncio.create_subprocess_exec(
            "systemd-run", "--user", "--on-active=2", "--timer-property=AccuracySec=100ms",
            "systemctl", "--user", "restart", "radiokiosk.service", **quiet)

    def _point_service_at(self, checkout, link):
        """Let the service and the menu entry start from the link instead of the checkout."""
        for path in (UNIT, *ENTRIES):
            try:
                text = path.read_text()
            except OSError:
                continue
            changed = text.replace(f"WorkingDirectory={checkout}\n", f"WorkingDirectory={link}\n") \
                          .replace(f"Exec={checkout}/radiokiosk-ui", f"Exec={link}/radiokiosk-ui")
            if changed != text:
                path.write_text(changed)

    async def pull(self):
        """For development: the newest commit of the branch instead of a release, without a guard."""
        if not self.installed():
            raise RuntimeError("update failed: this is not an installed copy")
        checkout, versions, link = await self.find_places()
        code, out = await run("git", "-C", str(checkout), "pull", "--ff-only", timeout=120)
        if code:
            raise RuntimeError("update failed – is there an internet connection?")
        changed = "Already up to date" not in out and "Bereits aktuell" not in out
        if link.is_symlink() and link.resolve() != checkout.resolve():
            turn(link, checkout)
            changed = True
        if changed:
            await asyncio.create_subprocess_exec(
                "systemd-run", "--user", "--on-active=2", "--timer-property=AccuracySec=100ms",
                "systemctl", "--user", "restart", "radiokiosk.service",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        return changed

    # --- in the background ---------------------------------------------

    async def run(self):
        """Look for a release once a day; with the setting on, install it at night while nothing plays."""
        await self.started()
        await asyncio.sleep(random.uniform(60, 600))   # not all devices at once after a power cut
        while True:
            try:
                if time.time() - self.checked > CHECK_EVERY:
                    await self.check()
                night = NIGHT[0] <= time.localtime().tm_hour < NIGHT[1]
                wanted = self.available and self.available["version"] != self.failed
                if self.cfg["auto_update"] and wanted and night and self.core.active is None and self.installed():
                    await self.apply()
            except RuntimeError:
                pass   # no connection or no luck: the next round tries again
            await asyncio.sleep(random.uniform(1500, 2100))
