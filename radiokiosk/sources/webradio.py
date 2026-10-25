"""Internet radio: station directory from radio-browser.info, playback through mpv."""

import aiohttp

from ..config import load_json, save_json

SERVERS = ["de1.api.radio-browser.info", "de2.api.radio-browser.info", "all.api.radio-browser.info"]
HEADERS = {"User-Agent": "RadioKiosk/0.1"}
KEEP_SEARCHES = 30
PAGE = 60   # stations per page; the next page comes with "load more"
MANY_TAGS = 20   # a station with more tags than this puts itself into every genre; real ones have up to about 15

# Genres as the directory's tags. Stations tag themselves, so one genre asks for the usual spellings,
# and a tag matches as a part ("rock" finds "classic rock"); one with "=" must match whole ("ard", not "standard").
GENRES = {
    "pop": ["pop"],
    "rock": ["rock"],
    "charts": ["charts", "top 40", "hits"],
    "news": ["news"],
    "talk": ["talk", "culture", "kultur", "information"],
    "public": ["public radio", "public service", "=ard", "=orf"],
    "schlager": ["schlager"],
    "folk_de": ["volksmusik", "volkstümlich", "blasmusik"],
    "oldies": ["oldies", "classic hits"],
    "70s": ["70s", "70er"],
    "80s": ["80s", "80er"],
    "90s": ["90s", "90er"],
    "2000s": ["2000s", "00s", "2000er"],
    "dance": ["dance", "electronic", "techno", "house"],
    "chill": ["chill", "lounge", "ambient"],
    "hiphop": ["hiphop", "hip hop", "hip-hop", "=rap"],
    "alternative": ["alternative", "indie"],
    "metal": ["metal"],
    "jazz": ["jazz"],
    "soul": ["soul", "funk", "blues", "rnb"],
    "classical": ["classical", "klassik"],
    "country": ["country", "folk"],
    "world": ["reggae", "latin", "world music"],
    "christian": ["christian", "christlich", "worship", "gospel"],
    "kids": ["kids", "kinder", "children"],
    "sport": ["sport"],
    "comedy": ["comedy", "hörspiel", "hörbuch", "audiobook"],
    "regional": ["regional", "local", "lokal"],
    "christmas": ["christmas", "weihnacht", "xmas"],
}
LANGUAGES = {"de": "german", "en": "english"}


class Webradio:
    name = "webradio"

    def __init__(self, core):
        self.core = core
        self.station = None
        self.found = load_json("stations.json", {})   # search -> stations, for when the directory is away

    async def search(self, query="", genre="", scope="", lang="de", page=0):
        """Stations by name or genre, or the most popular ones; each by popularity, PAGE at a time.
        scope "country" keeps to the country set, "language" to stations in the language of the
        display, anything else asks the whole world. A search by words finds names first, then
        stations with a genre of that name. A list fetched before is given again when the
        directory cannot be reached, so a short outage does not empty the screen."""
        base = {"hidebroken": "true", "order": "clickcount", "reverse": "true"}
        if scope == "country":
            base["countrycode"] = self.core.cfg["country"]
        elif scope == "language":
            base["language"] = LANGUAGES.get(lang, "german")
        if genre:
            if genre not in GENRES:
                raise ValueError("no such genre")
            asks = [{"tag": tag.lstrip("="), **({"tagExact": "true"} if tag.startswith("=") else {})} for tag in GENRES[genre]]
        elif query:
            asks = [{"name": query}, {"tag": query}]
        else:
            asks = [{}]
        key = "|".join([query.lower(), genre, base.get("countrycode", ""), base.get("language", ""), str(page)])
        # Each ask brings its first pages in full, so the page asked for is right in the merged list as well.
        # One genre's tags are mixed by popularity; a search keeps the names before the genres. Stations
        # in every genre are left out where a genre is asked for; when that leaves a page short, ask for more.
        end, limit = PAGE * (page + 1), PAGE * (page + 1) * 5 // 4 + 10
        async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as http:
            for _ in range(3):
                try:
                    answers = [await self.ask(http, {**base, **ask, "limit": str(limit)}) for ask in asks]
                except RuntimeError:
                    if key in self.found:
                        return self.found[key]
                    raise
                rows, seen = [], set()
                for ask, answer in zip(asks, answers):
                    for s in answer:
                        if s["stationuuid"] in seen or ("tag" in ask and s.get("tags", "").count(",") >= MANY_TAGS):
                            continue
                        seen.add(s["stationuuid"])
                        rows.append(s)
                if len(rows) >= end or all(len(a) < limit for a in answers):
                    break
                limit *= 2
        if genre:
            rows.sort(key=lambda s: -s.get("clickcount", 0))
        found = [{
            "id": s["stationuuid"],
            "name": s["name"].strip(),
            "url": s.get("url_resolved") or s["url"],
            "logo": s.get("favicon") or "",
            "info": ", ".join(filter(None, [s.get("countrycode"), s.get("codec"),
                                            f'{s["bitrate"]} kbit/s' if s.get("bitrate") else ""])),
        } for s in rows[PAGE * page:PAGE * (page + 1)]]
        self.remember(key, found)
        return found

    @staticmethod
    async def ask(http, params):
        for server in SERVERS * 2:   # the servers take turns being slow; a second round costs little
            try:
                async with http.get(f"https://{server}/json/stations/search", params=params) as r:
                    r.raise_for_status()
                    return await r.json()
            except (aiohttp.ClientError, TimeoutError, ValueError):
                continue
        raise RuntimeError("station directory unreachable")

    def remember(self, key, found):
        self.found[key] = found
        kept = lambda k: k.startswith("||") and k.endswith("|0")   # the first page of a popular list
        while len(self.found) > KEEP_SEARCHES:
            self.found.pop(next((k for k in self.found if not kept(k)), next(iter(self.found))))
        if kept(key):   # only the popular lists are worth keeping over a restart
            save_json("stations.json", {k: v for k, v in self.found.items() if kept(k)})

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
