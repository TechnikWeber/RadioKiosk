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
# Feeds the reader offers with one tap: large German news sites and one for the world.
# They are the public feeds these sites publish for readers like this one; shown are
# headline and teaser as the feed carries them.
SUGGESTIONS = [
    {"url": "https://www.tagesschau.de/index~rss2.xml", "title": "tagesschau.de"},
    {"url": "https://www.spiegel.de/schlagzeilen/index.rss", "title": "DER SPIEGEL"},
    {"url": "https://www.zdf.de/rss/zdf/nachrichten", "title": "ZDFheute"},
    {"url": "https://www.deutschlandfunk.de/nachrichten-100.rss", "title": "Deutschlandfunk"},
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml", "title": "BBC News (World)"},
]
# what the reader starts with, by country; anything else gets the English one
STARTERS = {"DE": SUGGESTIONS[0], None: SUGGESTIONS[-1]}


def plain(markup, limit=None):
    """Text of a snippet of HTML, as feeds carry it in their descriptions."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text if limit is None or len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


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
        self.feeds = load_json("feeds.json", None)
        if self.feeds is None:
            self.feeds = [dict(STARTERS.get(cfg.get("country"), STARTERS[None]))]
        self.fetched = {}   # url -> (time, articles)

    async def _articles(self, feed):
        cached = self.fetched.get(feed["url"])
        if cached and time.time() - cached[0] < REFRESH_AFTER:
            return cached[1]
        try:
            parsed = await fetch_feed(feed["url"])
        except RuntimeError:
            return cached[1] if cached else []   # keep showing what was read last
        # some feeds repeat the headline as the text
        articles = [{"id": i["id"], "title": i["title"], "summary": "" if i["summary"] == i["title"] else i["summary"],
                     "date": i["date"],
                     "link": i["link"], "source": feed["title"]} for i in parsed["items"] if i["title"]]
        self.fetched[feed["url"]] = (time.time(), articles)
        return articles

    async def articles(self):
        """The newest articles of all feeds, newest first."""
        lists = await asyncio.gather(*(self._articles(feed) for feed in self.feeds))
        merged = sorted((a for articles in lists for a in articles), key=lambda a: -a["date"])
        return merged[:ARTICLES]

    def suggestions(self):
        return [s for s in SUGGESTIONS if all(feed["url"] != s["url"] for feed in self.feeds)]

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
