"""Internet radio: station directory from radio-browser.info, playback through mpv."""

import aiohttp

from ..config import load_json, save_json

SERVERS = ["de1.api.radio-browser.info", "de2.api.radio-browser.info", "all.api.radio-browser.info"]
HEADERS = {"User-Agent": "RadioKiosk/0.1"}
KEEP_SEARCHES = 30


class Webradio:
    name = "webradio"

    def __init__(self, core):
        self.core = core
        self.station = None
        self.found = load_json("stations.json", {})   # search -> stations, for when the directory is away

    async def search(self, query=""):
        """Stations by name, or the most popular of the country. A list fetched before is given
        again when the directory cannot be reached, so a short outage does not empty the screen."""
        params = {"limit": "60", "hidebroken": "true", "order": "clickcount", "reverse": "true"}
        if query:
            params["name"] = query
        else:
            params["countrycode"] = self.core.cfg["country"]
        key = f"{query.lower()}|{params.get('countrycode', '')}"
        async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as http:
            for server in SERVERS * 2:   # the servers take turns being slow; a second round costs little
                try:
                    async with http.get(f"https://{server}/json/stations/search", params=params) as r:
                        r.raise_for_status()
                        rows = await r.json()
                except (aiohttp.ClientError, TimeoutError, ValueError):
                    continue
                found = [{
                    "id": s["stationuuid"],
                    "name": s["name"].strip(),
                    "url": s.get("url_resolved") or s["url"],
                    "logo": s.get("favicon") or "",
                    "info": ", ".join(filter(None, [s.get("countrycode"), s.get("codec"),
                                                    f'{s["bitrate"]} kbit/s' if s.get("bitrate") else ""])),
                } for s in rows]
                self.remember(key, found)
                return found
        if key in self.found:
            return self.found[key]
        raise RuntimeError("station directory unreachable")

    def remember(self, key, found):
        self.found[key] = found
        while len(self.found) > KEEP_SEARCHES:
            self.found.pop(next(k for k in self.found if not k.startswith("|")))   # the popular list stays
        if key.startswith("|"):   # only the popular list is worth keeping over a restart
            save_json("stations.json", {key: found})

    async def play(self, station):
        if not str(station.get("url", "")).startswith(("http://", "https://")):   # the player would open files and devices as well
            raise ValueError("this is not an address")
        async with self.core.lock:
            await self.core.take(self)
            self.station = station
            self.core.update(source=self.name, status="loading", title=station["name"], text="",
                             error=None, detail={"id": station["id"]})
            self.core.remember("webradio", station["name"], station=station)
            try:
                await self.core.mpv.play(station["url"])
            except (RuntimeError, OSError) as e:
                self.core.fail(str(e))   # otherwise the station would stay on "loading"

    def on_title(self, title):
        # mpv reports the URL or file name until the stream sends a real title
        if self.station and title and title not in self.station["url"]:
            self.core.update(text=title)

    async def stop(self):
        self.station = None
