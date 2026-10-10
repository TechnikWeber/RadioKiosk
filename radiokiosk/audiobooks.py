"""Audiobooks from LibriVox: books in the public domain, read by volunteers.

They are looked up and fetched through the Internet Archive, which hosts them
and has the better search; neither needs a key. Chapters are played like the
episodes of a podcast, so a book continues where it stopped.
"""

import re

import aiohttp

from .config import load_json, save_json
from .feeds import HEADERS

SEARCH = "https://archive.org/advancedsearch.php"
BOOK = "https://archive.org/metadata/"
# what the archive calls the languages, by the country set for RadioKiosk
LANGUAGES = {"DE": "German OR ger OR deu", "AT": "German OR ger OR deu", "CH": "German OR ger OR deu",
             "FR": "French OR fre OR fra", "ES": "Spanish OR spa", "IT": "Italian OR ita", "NL": "Dutch OR dut OR nld"}
ENGLISH = "English OR eng"


class Shelf:
    """The books somebody has started or wants to hear."""

    def __init__(self):
        self.books = load_json("audiobooks.json", [])

    def keep(self, book, on):
        self.books = [b for b in self.books if b["id"] != book["id"]]
        if on:
            self.books.append({k: str(book.get(k, "")) for k in ("id", "title", "author", "language")})
            self.books.sort(key=lambda b: b["title"].lower())
        save_json("audiobooks.json", self.books)


async def _json(url, params=None):
    try:
        async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as http:
            async with http.get(url, params=params) as r:
                r.raise_for_status()
                return await r.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError):
        raise RuntimeError("the audiobook library cannot be reached")


def _text(value):
    return ", ".join(value) if isinstance(value, list) else str(value or "")


async def search(country, query=""):
    """Books matching `query` in any language; without one, the most heard in the own language."""
    query = re.sub(r"[^\w\s'-]", " ", query).strip()
    wanted = (f"(title:({query}) OR creator:({query}))" if query
              else f"language:({LANGUAGES.get(country.upper(), ENGLISH)})")
    data = await _json(SEARCH, [("q", f"collection:librivoxaudio AND {wanted}"), ("fl[]", "identifier"), ("fl[]", "title"),
                                ("fl[]", "creator"), ("fl[]", "language"), ("rows", "40"), ("output", "json"),
                                ("sort[]", "downloads desc")])
    return [{"id": d["identifier"], "title": _text(d.get("title")), "author": _text(d.get("creator")),
             "language": _text(d.get("language"))} for d in data.get("response", {}).get("docs", []) if d.get("identifier")]


def _seconds(length):
    """The archive gives a length as seconds or as mm:ss."""
    try:
        parts = [float(p) for p in str(length).split(":")]
    except ValueError:
        return 0
    return int(sum(part * 60 ** i for i, part in enumerate(reversed(parts))))


def chapters_of(book_id, data):
    """The chapters of a book from the archive's description of it, in reading order."""
    files = [f for f in data.get("files", []) if f.get("name", "").lower().endswith(".mp3")]
    # every chapter exists in several qualities; the small one is plenty for speech
    small = [f for f in files if f.get("format") == "64Kbps MP3"]
    chosen = sorted(small or files, key=lambda f: f["name"])
    return {"title": _text(data.get("metadata", {}).get("title")), "episodes": [
        {"id": f"{book_id}/{f['name']}", "title": f.get("title") or f["name"], "date": 0, "summary": "",
         "seconds": _seconds(f.get("length", 0)), "audio": f"https://archive.org/download/{book_id}/{f['name']}"}
        for f in chosen]}


async def chapters(book_id):
    if not re.fullmatch(r"[\w.-]+", book_id):
        raise ValueError("unknown book")
    return chapters_of(book_id, await _json(BOOK + book_id))
