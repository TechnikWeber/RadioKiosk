"""Smart home, kept as general as it gets: switches that call an address, and fields that show what an address answers.

Nearly everything in a home network can be reached over HTTP: a webhook of
Home Assistant, ioBroker or Node-RED, a Shelly or Tasmota plug directly. So a
switch is a name and an address that is called when it is tapped, and a field
is a name and an address whose answer is shown. The other direction needs
nothing here: RadioKiosk's own interface over HTTP is described in docs/api.md.

The calls are made by the service, not by the browser, so they work the same
from the display and from a phone on remote control.
"""

import asyncio
import json
import time
import uuid

import aiohttp

from .config import load_json, save_json

MOST = 40
TIMEOUT = 8
TRUST = 30            # seconds a field's value is shown before it is asked for again
VALUE_LENGTH = 60
METHODS = ("GET", "POST")


def pick(text, path):
    """What a field shows of an answer: the whole text, or one value out of JSON by its path (a.b.0.c)."""
    if path:
        try:
            value = json.loads(text)
            for step in path.split("."):
                value = value[int(step)] if isinstance(value, list) else value[step]
        except (ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError("the answer does not have this value")
        if isinstance(value, float):
            value = round(value, 2)
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return " ".join(str(text).split())[:VALUE_LENGTH]


class SmartHome:
    def __init__(self):
        self.items = load_json("smarthome.json", [])
        self.values = {}   # field id -> (time, value or None, problem or None)

    def clean(self, entry):
        """A switch or field as it is kept; raises ValueError where name or address make no sense."""
        kind = entry.get("kind") if entry.get("kind") in ("switch", "field") else "switch"
        name, url = str(entry.get("name", "")).strip()[:40], str(entry.get("url", "")).strip()
        if not name:
            raise ValueError("a name is needed")
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("this is not an address")
        item = {"kind": kind, "name": name, "url": url, "token": str(entry.get("token", "")).strip()}
        if kind == "switch":
            item.update(method=entry.get("method") if entry.get("method") in METHODS else "POST",
                        body=str(entry.get("body", "")).strip()[:2000], confirm=bool(entry.get("confirm")))
        else:
            item.update(path=str(entry.get("path", "")).strip()[:100], unit=str(entry.get("unit", "")).strip()[:10])
        return item

    def save(self, entry):
        item = self.clean(entry)
        known = next((i for i in self.items if i["id"] == entry.get("id")), None)
        if known is None:
            if len(self.items) >= MOST:
                raise ValueError("there are too many entries already")
            known = {"id": uuid.uuid4().hex[:12]}
            self.items.append(known)
        if entry.get("token") is None and known.get("token"):   # the interface never gets the token back, so "unchanged" keeps it
            item["token"] = known["token"]
        known.update(item)
        self.values.pop(known["id"], None)
        save_json("smarthome.json", self.items)

    def remove(self, item_id):
        self.items = [i for i in self.items if i["id"] != item_id]
        save_json("smarthome.json", self.items)

    async def call(self, item, method="GET", body=""):
        headers = {"Authorization": f"Bearer {item['token']}"} if item.get("token") else {}
        if body:
            headers["Content-Type"] = "application/json" if body.lstrip()[:1] in "{[" else "text/plain"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as http:
                async with http.request(method, item["url"], headers=headers, data=body.encode() or None) as reply:
                    text = await reply.text(errors="replace")
                    if reply.status >= 400:
                        raise RuntimeError(f"the device answered with error {reply.status}")
                    return text
        except (aiohttp.ClientError, TimeoutError, OSError):
            raise RuntimeError("the device did not answer")

    async def press(self, item_id):
        item = next((i for i in self.items if i["id"] == item_id and i["kind"] == "switch"), None)
        if item is None:
            raise KeyError("no such switch")
        await self.call(item, item["method"], item.get("body", "") if item["method"] == "POST" else "")
        self.values.clear()   # what was switched may show in a field

    async def value(self, item):
        known = self.values.get(item["id"])
        if known and time.time() - known[0] < TRUST:
            return known[1:]
        try:
            found = (pick(await self.call(item), item.get("path", "")), None)
        except RuntimeError as problem:
            found = (None, str(problem))
        self.values[item["id"]] = (time.time(), *found)
        return found

    async def listing(self):
        """Everything for the interface: the fields with what they show just now, and no token."""
        fields = [i for i in self.items if i["kind"] == "field"]
        values = dict(zip((f["id"] for f in fields), await asyncio.gather(*(self.value(f) for f in fields))))
        shown = []
        for item in self.items:
            entry = {k: v for k, v in item.items() if k != "token"}
            entry["has_token"] = bool(item.get("token"))
            if item["kind"] == "field":
                entry["value"], entry["problem"] = values[item["id"]]
            shown.append(entry)
        return shown
