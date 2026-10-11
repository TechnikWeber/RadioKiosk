"""Sound from what yt-dlp can find and open, played through mpv.

yt-dlp is not part of RadioKiosk: it is used
where the system has it, or fetched on request as the project's own single file into
the configuration folder, where it can also be renewed. The sites it reads change
often, so an old yt-dlp is the usual reason for this to stop working.
"""

import asyncio
import json
import os
import shutil
import stat
import sys
import time

import aiohttp

from ..config import CONFIG_DIR, load_json, save_json

PROGRAM = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"   # runs with the system's Python
OWN = CONFIG_DIR / "bin" / "yt-dlp"
RESULTS = 15
SEARCH_TIMEOUT = 45
OPEN_TIMEOUT = 60     # a small computer needs a good ten seconds to find the stream of one title
KEPT = 100
SEARCHES = 30
WATCH_EVERY = 5
RENEW_AFTER = 7 * 86400   # a fetched yt-dlp older than this is replaced by the newest
LOOK_EVERY = 6 * 3600


def program():
    """How to start yt-dlp, as a list; None where there is none. The fetched copy goes first: it is the newer one."""
    if OWN.exists():
        return [sys.executable, str(OWN)]
    found = shutil.which("yt-dlp")
    return [found] if found else None


async def call(*arguments, timeout):
    command = program()
    if command is None:
        raise RuntimeError("yt-dlp is not installed")
    proc = await asyncio.create_subprocess_exec(*command, "--no-warnings", "--ignore-config", *arguments,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("yt-dlp took too long")
    if proc.returncode:
        raise RuntimeError("yt-dlp failed: " + (err.decode(errors="replace").strip().splitlines() or ["no reason given"])[-1][:200])
    return out.decode(errors="replace")


async def version():
    try:
        return (await call("--version", timeout=30)).strip()
    except RuntimeError:
        return None


async def fetch():
    """Get the newest yt-dlp from its project into the configuration folder; returns its version."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as http:
            async with http.get(PROGRAM) as reply:
                reply.raise_for_status()
                data = await reply.read()
    except (aiohttp.ClientError, TimeoutError):
        raise RuntimeError("yt-dlp could not be fetched – is there an internet connection?")
    if not data.startswith(b"#!"):
        raise RuntimeError("yt-dlp could not be fetched: this is not the program")
    OWN.parent.mkdir(parents=True, exist_ok=True)
    partial = OWN.with_name(OWN.name + ".part")
    partial.write_bytes(data)
    partial.chmod(partial.stat().st_mode | stat.S_IXUSR)
    try:   # only a copy that runs replaces the one that is there
        proc = await asyncio.create_subprocess_exec(sys.executable, str(partial), "--version",
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(proc.communicate(), 60)
    except (OSError, asyncio.TimeoutError):
        out, proc = b"", None
    if proc is None or proc.returncode:
        partial.unlink(missing_ok=True)
        raise RuntimeError("yt-dlp could not be fetched: the new copy does not start")
    os.replace(partial, OWN)
    return out.decode().strip()


async def keep_fresh():
    """Renew a fetched yt-dlp once a week. One that came with the system is the system's business."""
    while True:
        await asyncio.sleep(600)   # not while the computer is still starting
        try:
            if OWN.exists() and time.time() - OWN.stat().st_mtime > RENEW_AFTER:
                await fetch()
        except (RuntimeError, OSError):
            pass   # no connection just now: the next look comes
        await asyncio.sleep(LOOK_EVERY)


def entry(raw):
    """One title as the interface lists it; None for what cannot be played (a channel, a deleted title)."""
    address = raw.get("webpage_url") or raw.get("url")
    if not address or not raw.get("title") or raw.get("_type") == "playlist" or raw.get("ie_key") == "YoutubeTab":
        return None
    return {"id": str(raw.get("id") or address), "title": raw["title"], "url": address,
            "author": raw.get("channel") or raw.get("uploader") or "", "seconds": int(raw.get("duration") or 0),
            "date": int(raw.get("timestamp") or raw.get("release_timestamp") or 0),
            "live": bool(raw.get("is_live") or raw.get("live_status") == "is_live")}


async def listing(target, *arguments):
    out = await call("--flat-playlist", "--dump-single-json", "--playlist-end", "50", *arguments, target, timeout=SEARCH_TIMEOUT)
    try:
        data = json.loads(out)
    except ValueError:
        raise RuntimeError("yt-dlp failed: no usable answer")
    rows = data.get("entries") if isinstance(data.get("entries"), list) else [data]
    return [e for e in (entry(r) for r in rows if isinstance(r, dict)) if e]


async def search(query, language="en"):
    """Titles for some words, or what lies behind an address: one title or the titles of a list."""
    query = query.strip()
    if not query:
        return []
    target = query if query.startswith(("http://", "https://")) else f"ytsearch{RESULTS}:{query}"
    language = language if language.isalpha() and len(language) == 2 else "en"
    # A list tells when a title appeared only roughly ("3 days ago"), and yt-dlp can read that only in
    # English, where the titles come translated. So it is asked twice at once: for the titles in the
    # user's language, and for the dates, which are left out if that second answer fails.
    titles, dates = await asyncio.gather(
        listing(target, "--extractor-args", f"youtube:lang={language}"),
        listing(target.replace(f"ytsearch{RESULTS}:", f"ytsearch{2 * RESULTS}:"),   # the two lists differ; more of this one, more matches
                "--extractor-args", "youtubetab:approximate_date"), return_exceptions=True)
    if isinstance(titles, BaseException):
        raise titles
    when = {e["id"]: e["date"] for e in dates} if isinstance(dates, list) else {}
    return [{**e, "date": e["date"] or when.get(e["id"], 0)} for e in titles]


_when = {}


async def when(address):
    """The moment one title appeared, exactly, by opening it: for the titles a list gave no day for. 0 if unknown."""
    if address not in _when:
        try:
            out = await call("--print", "%(timestamp)s", "--skip-download", "--no-playlist", address, timeout=OPEN_TIMEOUT)
            _when[address] = int(float(out.strip().splitlines()[0]))
        except (RuntimeError, ValueError, IndexError):
            return 0
    return _when[address]


class Media:
    name = "media"

    def __init__(self, core):
        self.core = core
        self.kept = load_json("media.json", [])
        self.searches = load_json("media_searches.json", [])   # search words kept to be run again, newest first
        self.item = None
        self.watch = None
        self.retried = None   # id of the title that was already opened a second time

    def keep(self, item, on):
        self.kept = [k for k in self.kept if k["id"] != item["id"]]
        if on:
            self.kept.insert(0, {k: item.get(k, "") for k in ("id", "title", "url", "author", "seconds", "live", "date")})
        self.kept = self.kept[:KEPT]
        save_json("media.json", self.kept)

    def keep_search(self, query, on):
        query = " ".join(query.split())[:200]
        self.searches = [s for s in self.searches if s.lower() != query.lower()]
        if on and query:
            self.searches.insert(0, query)
        self.searches = self.searches[:SEARCHES]
        save_json("media_searches.json", self.searches)

    async def play(self, item, again=False):
        async with self.core.lock:
            if again and self.item is not item:   # stopped in the meantime
                return
            await self.core.take(self)
            self._end_watch()
            self.item = item
            if not again:
                self.retried = None
            self.core.update(source=self.name, status="loading", title=item["title"], text=item.get("author", ""),
                             error=None, detail={"id": item["id"]})
            self.core.remember("media", item["title"], item=item)
            try:
                # sound only: the best audio where there is one on its own, else the smallest whole stream
                stream = (await call("-f", "bestaudio/worst", "--get-url", "--no-playlist", item["url"],
                                     timeout=OPEN_TIMEOUT)).strip().splitlines()
                if not stream:
                    raise RuntimeError("yt-dlp failed: no stream found")
                if self.item is not item:   # stopped or something else chosen while yt-dlp was looking
                    return
                await self.core.mpv.play(stream[0], "vid=no")
            except (RuntimeError, OSError) as e:
                self.core.fail(str(e))
                return
            self.watch = asyncio.create_task(self._watch(item))

    async def _watch(self, item):
        """Show how far the title has played, and end the source when it is over."""
        started = False
        while True:
            await asyncio.sleep(WATCH_EVERY)
            try:
                position = (await self.core.mpv.command("get_property", "time-pos")).get("data")
                length = (await self.core.mpv.command("get_property", "duration")).get("data")
            except (RuntimeError, asyncio.TimeoutError, AttributeError):
                continue
            if position is None:
                if started:
                    asyncio.create_task(self.core.stop())
                    return
                continue
            started = True
            self.core.update(detail={"id": item["id"], "position": round(position), "length": round(length or 0)})

    def on_playback_error(self):
        """The address yt-dlp found is sometimes refused; a second look gets another one. Once per title."""
        if self.item is None or self.retried == self.item["id"]:
            return False
        self.retried = self.item["id"]
        asyncio.create_task(self.play(self.item, again=True))
        return True

    async def seek(self, seconds):
        if self.core.active is self:
            await self.core.mpv.command("seek", seconds, "relative")

    def on_title(self, title):
        pass

    def _end_watch(self):
        if self.watch and not self.watch.done() and self.watch is not asyncio.current_task():
            self.watch.cancel()
        self.watch = None

    async def stop(self):
        self._end_watch()
        self.item = None
