"""Podcasts: found through a directory, played from their own feed through mpv.

Three directories are supported. fyyd and Apple need no key; the Podcast Index
is free too, but wants a key and a secret from podcastindex.org.
"""

import asyncio
import hashlib
import time

import aiohttp

from ..config import load_json, save_json
from ..feeds import HEADERS, fetch_feed

PROVIDERS = ("fyyd", "apple", "podcastindex")
EPISODES = 100
SAVE_EVERY = 5      # seconds between notes of the playing position
REWIND = 5          # seconds an episode steps back when it is picked up again


async def _json(url, params, headers=None):
    try:
        async with aiohttp.ClientSession(headers={**HEADERS, **(headers or {})},
                                         timeout=aiohttp.ClientTimeout(total=12)) as http:
            async with http.get(url, params=params) as r:
                if r.status in (401, 403):
                    raise RuntimeError("the podcast directory refused the key")
                r.raise_for_status()
                return await r.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError):
        raise RuntimeError("podcast directory unreachable")


async def search(cfg, query):
    """Podcasts matching `query`, the same shape whichever directory answers."""
    provider = cfg["podcast_provider"]
    if provider == "apple":
        data = await _json("https://itunes.apple.com/search",
                           {"media": "podcast", "term": query, "limit": "40", "country": cfg["country"]})
        rows = [(r.get("collectionName"), r.get("artistName"), r.get("feedUrl"), r.get("artworkUrl100"))
                for r in data.get("results", [])]
    elif provider == "podcastindex":
        key, secret = cfg["podcast_key"].strip(), cfg["podcast_secret"].strip()
        if not key or not secret:
            raise RuntimeError("the Podcast Index needs a key and a secret")
        now = str(int(time.time()))
        data = await _json("https://api.podcastindex.org/api/1.0/search/byterm", {"q": query, "max": "40"}, {
            "X-Auth-Key": key, "X-Auth-Date": now,
            "Authorization": hashlib.sha1((key + secret + now).encode()).hexdigest()})
        rows = [(f.get("title"), f.get("author"), f.get("url"), f.get("image")) for f in data.get("feeds", [])]
    else:
        data = await _json("https://api.fyyd.de/0.2/search/podcast", {"title": query, "count": "40"})
        rows = [(p.get("title"), p.get("author"), p.get("xmlURL"), p.get("smallImageURL") or p.get("imgURL"))
                for p in data.get("data", [])]
    return [{"title": title.strip(), "author": (author or "").strip(), "feed": feed, "image": image or ""}
            for title, author, feed, image in rows if title and feed]


class Podcasts:
    name = "podcast"

    def __init__(self, core):
        self.core = core
        self.subscribed = load_json("podcasts.json", [])
        self.positions = load_json("podcast_positions.json", {})   # episode id -> seconds heard
        self.episode = None
        self.watch = None

    def subscribe(self, podcast, on):
        self.subscribed = [p for p in self.subscribed if p["feed"] != podcast["feed"]]
        if on:
            self.subscribed.append({k: podcast.get(k, "") for k in ("title", "author", "feed", "image")})
            self.subscribed.sort(key=lambda p: p["title"].lower())
        save_json("podcasts.json", self.subscribed)

    async def episodes(self, feed):
        parsed = await fetch_feed(feed)
        return {"title": parsed["title"], "episodes": [
            {"id": i["id"], "title": i["title"], "date": i["date"], "seconds": i["seconds"], "audio": i["audio"],
             "summary": i["summary"], "heard": round(self.positions.get(i["id"], 0))}
            for i in parsed["items"] if i["audio"]][:EPISODES]}

    async def play(self, episode):
        """episode: id, title, audio and the podcast's title."""
        async with self.core.lock:
            await self.core.take(self)
            self._end_watch()
            self.episode = episode
            self.core.update(source=self.name, status="loading", title=episode.get("podcast") or "Podcast",
                             text=episode["title"], error=None, detail={"id": episode["id"]})
            self.core.remember("podcast", episode["title"], episode=episode)
            start = max(0, self.positions.get(episode["id"], 0) - REWIND)
            await self.core.mpv.play(episode["audio"], f"start={start}" if start else "")
            self.watch = asyncio.create_task(self._watch(episode))

    async def _watch(self, episode):
        """Note how far the episode has been heard, and end the source when it is over."""
        started = False
        while True:
            await asyncio.sleep(SAVE_EVERY)
            try:
                position = (await self.core.mpv.command("get_property", "time-pos")).get("data")
                length = (await self.core.mpv.command("get_property", "duration")).get("data")
            except (RuntimeError, asyncio.TimeoutError, AttributeError):
                continue
            if position is None:
                if started:   # played to its end: next time it starts from the beginning
                    self.positions.pop(episode["id"], None)
                    save_json("podcast_positions.json", self.positions)
                    asyncio.create_task(self.core.stop())
                    return
                continue
            started = True
            self.positions[episode["id"]] = position
            save_json("podcast_positions.json", self.positions)
            self.core.update(detail={"id": episode["id"], "position": round(position), "length": round(length or 0)})

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
        self.episode = None
