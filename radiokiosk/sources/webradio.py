"""Internet radio: station directory from radio-browser.info, playback through mpv."""

import aiohttp

SERVERS = ["de1.api.radio-browser.info", "de2.api.radio-browser.info", "all.api.radio-browser.info"]
HEADERS = {"User-Agent": "RadioKiosk/0.1"}


class Webradio:
    name = "webradio"

    def __init__(self, core):
        self.core = core
        self.station = None

    async def search(self, query=""):
        params = {"limit": "60", "hidebroken": "true", "order": "clickcount", "reverse": "true"}
        if query:
            params["name"] = query
        else:
            params["countrycode"] = self.core.cfg["country"]
        last_error = None
        async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as http:
            for server in SERVERS:
                try:
                    async with http.get(f"https://{server}/json/stations/search", params=params) as r:
                        r.raise_for_status()
                        rows = await r.json()
                except (aiohttp.ClientError, TimeoutError) as e:
                    last_error = e
                    continue
                return [{
                    "id": s["stationuuid"],
                    "name": s["name"].strip(),
                    "url": s.get("url_resolved") or s["url"],
                    "logo": s.get("favicon") or "",
                    "info": ", ".join(filter(None, [s.get("countrycode"), s.get("codec"),
                                                    f'{s["bitrate"]} kbit/s' if s.get("bitrate") else ""])),
                } for s in rows]
        raise RuntimeError("station directory unreachable")

    async def play(self, station):
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
