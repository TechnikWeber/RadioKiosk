"""News feeds (RSS and Atom): a reader as a tile and the newest article on the idle screen.

parse_feed() is also what the podcast tile reads its episodes with.
"""

import asyncio
import datetime
import email.utils
import html
import re
import time
import xml.etree.ElementTree as ET

import aiohttp

from .config import load_json, save_json

HEADERS = {"User-Agent": "RadioKiosk/0.1"}
REFRESH_AFTER = 300     # seconds a fetched feed is trusted
ARTICLES = 60           # newest articles kept over all feeds
# Feeds the reader offers with one tap, in three groups. They are the public feeds
# these sites publish for readers like this one; shown are headline and teaser as the
# feed carries them. This list is the one thing here that cannot keep itself current,
# so every entry is tried before it is offered: one that is gone simply does not appear.
SUGGESTIONS = [
    {"url": "https://www.tagesschau.de/index~rss2.xml", "title": "tagesschau.de", "group": "news"},
    {"url": "https://www.spiegel.de/schlagzeilen/index.rss", "title": "DER SPIEGEL", "group": "news"},
    {"url": "https://www.zdf.de/rss/zdf/nachrichten", "title": "ZDFheute", "group": "news"},
    {"url": "https://www.deutschlandfunk.de/nachrichten-100.rss", "title": "Deutschlandfunk", "group": "news"},
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml", "title": "BBC News (World)", "group": "news"},
    {"url": "https://www.heise.de/rss/heise-atom.xml", "title": "heise online", "group": "tech"},
    {"url": "https://rss.golem.de/rss.php?feed=RSS2.0", "title": "Golem.de", "group": "tech"},
    {"url": "https://www.esa.int/rssfeed/Germany", "title": "ESA (Deutschland)", "group": "tech"},
    {"url": "https://www.esa.int/rssfeed/TopNews", "title": "ESA Top News", "group": "tech"},
    {"url": "https://www.nasa.gov/news-release/feed/", "title": "NASA", "group": "tech"},
    {"url": "https://hackaday.com/blog/feed/", "title": "Hackaday", "group": "tech"},
    {"url": "https://www.raspberrypi.com/news/feed/", "title": "Raspberry Pi News", "group": "tech"},
    {"url": "https://www.darc.de/rss.xml", "title": "DARC (Amateurfunk)", "group": "radio"},
    {"url": "https://www.arrl.org/arrl.rss", "title": "ARRL News", "group": "radio"},
    {"url": "https://rsgb.org/main/feed/", "title": "RSGB", "group": "radio"},
    {"url": "https://www.rtl-sdr.com/feed/", "title": "rtl-sdr.com", "group": "radio"},
]
CHECK_AFTER = 24 * 3600   # seconds until a suggestion is tried again
FIRST_WAIT = 4            # seconds the first list waits for the checks before it shows what is known


def plain(markup, limit=None):
    """Text of a snippet of HTML, as feeds carry it in their descriptions."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text if limit is None or len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


def real_text(summary, title):
    """The summary, or nothing where a feed only repeats the headline or gives a bare link."""
    return "" if summary == title or re.fullmatch(r"(https?://|www\.)\S+", summary) else summary


def moment(text):
    """Unix time of a feed's date, RFC 822 (RSS) or ISO 8601 (Atom); 0 if it cannot be read."""
    text = (text or "").strip()
    try:
        return email.utils.parsedate_to_datetime(text).timestamp()
    except (TypeError, ValueError):
        pass
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)).timestamp()
    except ValueError:
        return 0


def seconds(text):
    """Length of an episode: feeds write 3723, 62:03 or 1:02:03."""
    try:
        parts = [float(p) for p in (text or "").strip().split(":")]
    except ValueError:
        return 0
    return int(sum(part * 60 ** i for i, part in enumerate(reversed(parts)))) if parts else 0


def parse_feed(data):
    """Title, picture and items of an RSS 2.0, RSS 1.0 or Atom feed.

    The formats differ in namespaces more than in substance, so elements are
    matched by their local name.
    """
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise RuntimeError("this address does not deliver a feed")
    local = lambda element: element.tag.rsplit("}", 1)[-1]
    items, head = [], {}
    for element in root.iter():
        name = local(element)
        if name in ("item", "entry"):
            items.append(element)
        elif name in ("channel", "feed") and not head:
            head = {local(child): child for child in element if local(child) not in ("item", "entry")}
    if not head and not items:
        raise RuntimeError("this address does not deliver a feed")

    def first(fields, *names):
        return next((fields[n] for n in names if n in fields), None)

    def text(element):
        return (element.text or "").strip() if element is not None else ""

    picture = first(head, "image")
    result = {"title": plain(text(first(head, "title"))),
              "image": (picture.get("href") or text(picture.find("url"))) if picture is not None else "", "items": []}
    for item in items:
        fields = {}
        for child in item:
            fields.setdefault(local(child), child)
        link = first(fields, "link")
        audio = next((c.get("url") for c in item if local(c) == "enclosure" and c.get("type", "").startswith("audio")
                      or local(c) == "enclosure" and re.search(r"\.(mp3|m4a|ogg|opus|aac)(\?|$)", c.get("url", ""))), None)
        address = (link.get("href") or text(link)) if link is not None else ""
        result["items"].append({
            "id": text(first(fields, "guid", "id")) or address or audio or text(first(fields, "title")),
            "title": plain(text(first(fields, "title"))),
            "summary": plain(text(first(fields, "description", "summary", "encoded", "content")), 700),
            "date": moment(text(first(fields, "pubDate", "published", "updated", "date"))),
            "link": address, "audio": audio, "seconds": seconds(text(first(fields, "duration"))),
        })
    return result


async def fetch_feed(url):
    try:
        async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as http:
            async with http.get(url) as r:
                r.raise_for_status()
                return parse_feed(await r.read())
    except (aiohttp.ClientError, TimeoutError, ValueError):
        raise RuntimeError("this feed cannot be reached")


class Feeds:
    def __init__(self, cfg):
        # nothing is read until the user picks a feed; the suggestions are an offer, not a choice made for them
        self.feeds = load_json("feeds.json", [])
        self.fetched = {}   # url -> (time, articles)
        self.working = load_json("feed_suggestions.json", {"checked": 0, "urls": []})
        self.checking = None

    async def _articles(self, feed):
        cached = self.fetched.get(feed["url"])
        if cached and time.time() - cached[0] < REFRESH_AFTER:
            return cached[1]
        try:
            parsed = await fetch_feed(feed["url"])
        except RuntimeError:
            return cached[1] if cached else []   # keep showing what was read last
        articles = [{"id": i["id"], "title": i["title"], "summary": real_text(i["summary"], i["title"]),
                     "date": i["date"],
                     "link": i["link"], "source": feed["title"]} for i in parsed["items"] if i["title"]]
        self.fetched[feed["url"]] = (time.time(), articles)
        return articles

    async def articles(self):
        """The newest articles of all feeds, newest first."""
        lists = await asyncio.gather(*(self._articles(feed) for feed in self.feeds))
        merged = sorted((a for articles in lists for a in articles), key=lambda a: -a["date"])
        return merged[:ARTICLES]

    async def _check(self):
        """Try every suggestion and note which ones deliver a feed."""
        async def works(url):
            try:
                return bool((await fetch_feed(url))["items"])
            except RuntimeError:
                return False

        results = await asyncio.gather(*(works(s["url"]) for s in SUGGESTIONS))
        self.working = {"checked": time.time(), "urls": [s["url"] for s, ok in zip(SUGGESTIONS, results) if ok]}
        if self.working["urls"]:   # with no connection at all, keep what was known
            save_json("feed_suggestions.json", self.working)

    async def suggestions(self):
        """The suggestions that work and are not chosen yet. One that cannot be reached is left out without a word."""
        if time.time() - self.working["checked"] > CHECK_AFTER and (self.checking is None or self.checking.done()):
            self.checking = asyncio.create_task(self._check())
        if not self.working["urls"] and self.checking and not self.checking.done():
            try:   # the very first time: give the checks a moment rather than show an empty list
                await asyncio.wait_for(asyncio.shield(self.checking), FIRST_WAIT)
            except asyncio.TimeoutError:
                pass
        taken = {feed["url"] for feed in self.feeds}
        return [s for s in SUGGESTIONS if s["url"] in self.working["urls"] and s["url"] not in taken]

    async def add(self, url):
        url = url.strip()
        if not re.match(r"https?://", url):
            url = "https://" + url
        if any(feed["url"] == url for feed in self.feeds):
            return
        parsed = await fetch_feed(url)   # also proves that the address is a feed
        known = next((s["title"] for s in SUGGESTIONS if s["url"] == url), None)
        self.feeds.append({"url": url, "title": known or parsed["title"] or url.split("/")[2]})
        save_json("feeds.json", self.feeds)

    def remove(self, url):
        self.feeds = [feed for feed in self.feeds if feed["url"] != url]
        self.fetched.pop(url, None)
        save_json("feeds.json", self.feeds)
