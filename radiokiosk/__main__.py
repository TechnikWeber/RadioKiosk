"""HTTP API, WebSocket state feed and static web UI."""

import asyncio
import ipaddress
import logging
import socket
from pathlib import Path

import aiohttp
from aiohttp import web

from . import __version__, audio, bluetooth, device, network_audio
from .alarm import Alarm
from .config import WEB_DIR, load_config, save_setting
from .core import Core
from .sources.adsb import Adsb
from .sources.apps import Apps
from .sources.dab import SLIDES, Dab
from .sources.fm import Fm
from .sources.receiver import CHOICES, ENGINE_LOAD_LIMIT, available_backends, engine_load
from .sources.tuner import BANDS, Tuner
from .sources.webradio import Webradio
from .schedule import Schedule
from .feeds import Feeds
from .gallery import Gallery, subfolders
from .qsolog import BANDS as LOG_BANDS, MODES as LOG_MODES, QsoLog
from .sources.survey import RANGES, Survey, as_text
from .spaceweather import SpaceWeather
from .spots import Spots
from . import audiobooks, satellites as satellite_passes
from .alerts import Alerts
from .verses import Verses
from .sources.aprs import Aprs
from .sources.music import Music
from .sources import podcasts as podcast_directory
from .sources.ais import Ais
from .sources.podcasts import PROVIDERS, Podcasts
from .sources.sensors import Sensors
from .timer import Timer
from .weather import Weather, place_name


@web.middleware
async def errors(request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except (RuntimeError, KeyError, ValueError, OSError) as e:
        return web.json_response({"error": str(e) or type(e).__name__}, status=400)
    except aiohttp.ClientError:
        # some service on the internet did not answer; no source should let that through, but none may crash on it
        return web.json_response({"error": "a service on the internet cannot be reached"}, status=400)
    except Exception as e:   # a mistake in this program: say so readably instead of a bare server error
        logging.getLogger(__name__).exception("request %s failed", request.path)
        return web.json_response({"error": f"internal error: {type(e).__name__}"}, status=500)


def addresses(port):
    """How other devices in the network reach this one."""
    found = [f"http://{socket.gethostname().split('.')[0]}.local:{port}"]
    try:
        # no packet is sent; this only asks the system which address it would use
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            found.append(f"http://{probe.getsockname()[0]}:{port}")
    except OSError:
        pass
    return found


def _build_id():
    """Changes with every update, also one that keeps the version number: an open interface reloads when it differs."""
    files = (p for d in (WEB_DIR, WEB_DIR.parent / "radiokiosk") for p in d.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts)
    return f"{__version__}.{int(max(p.stat().st_mtime for p in files))}"


BUILD = _build_id()


def build(cfg):
    core = Core(cfg)

    @web.middleware
    async def local_first(request, handler):
        """Answer this computer always, the local network only when remote control is on."""
        client = ipaddress.ip_address(request.remote or "127.0.0.1")
        client = getattr(client, "ipv4_mapped", None) or client
        if client.is_loopback or (cfg["remote"] and (client.is_private or client.is_link_local)):
            return await handler(request)
        raise web.HTTPForbidden(text="Remote control is switched off on this RadioKiosk.")

    webradio, dab, fm, tuner, apps = Webradio(core), Dab(core), Fm(core), Tuner(core), Apps(core)
    adsb = Adsb(core)
    weather = Weather()
    gallery = Gallery(cfg)
    feeds = Feeds(cfg)
    space, log, survey, spots = SpaceWeather(), QsoLog(cfg), Survey(core), Spots()
    music, aprs, shelf, sky, alerts = Music(core), Aprs(core), audiobooks.Shelf(), satellite_passes.Satellites(), Alerts(core)
    verses = Verses(cfg)
    podcasts, sensors, ais = Podcasts(core), Sensors(core), Ais(core)
    alarm = Alarm(core)
    timer = Timer(core)
    schedule = Schedule()
    receivers = network_audio.Receivers(cfg)
    bt = bluetooth.Bluetooth()
    core.players = {
        "webradio": lambda last: webradio.play(last["station"]),
        "dab": lambda last: dab.play(last["sid"]),
        "fm": lambda last: fm.tune(last["mhz"]),
        "tuner": lambda last: tuner.tune(last["hz"], last["mode"], last.get("squelch", 0), 1, last["title"]),
        "podcast": lambda last: podcasts.play(last["episode"]),
        "music": lambda last: music.play(last["path"]),
    }
    core.sources.update(fm=fm, tuner=tuner)
    core.receiver_backends = available_backends()
    routes = web.RouteTableDef()
    ok = lambda **data: web.json_response({"ok": True, **data})

    @routes.get("/")
    async def index(request):
        return web.FileResponse(WEB_DIR / "index.html")

    @routes.get("/ws")
    async def ws(request):
        socket = web.WebSocketResponse(heartbeat=20)
        await socket.prepare(request)
        core.clients.add(socket)
        await socket.send_json(core.snapshot())
        try:
            async for _ in socket:
                pass
        finally:
            core.clients.discard(socket)
        return socket

    @routes.get("/api/clients")
    async def clients(request):
        """How many interfaces are connected; the kiosk start uses it to see whether the browser came up."""
        return web.json_response({"count": len(core.clients)})

    @routes.get("/api/state")
    async def state(request):
        return web.json_response(core.snapshot())

    @routes.post("/api/stop")
    async def stop(request):
        await core.stop()
        return ok()

    @routes.post("/api/volume")
    async def volume(request):
        await audio.set_volume((await request.json())["value"])
        await core.refresh_volume()
        return ok()

    @routes.post("/api/sleep")
    async def sleep(request):
        core.sleep_in(max(0, min(600, float((await request.json())["minutes"]))))
        return ok()

    @routes.post("/api/record")
    async def record(request):
        await core.record(bool((await request.json())["on"]))
        return ok()

    @routes.get("/live.mp3")
    async def live(request):
        return await network_audio.live_stream(request)

    @routes.get("/api/device")
    async def device_get(request):
        return web.json_response({
            # the chosen brightness, not what the idle screen has dimmed it to
            "brightness": cfg["brightness"] if device.brightness() is not None and cfg["brightness"] else device.brightness(),
            "power": await device.can_power_off(),
            "wifi": device.has_wifi(), "wifi_powersave": await device.wifi_powersave(),
            "update": device.can_update(), "version": __version__,
            "receivers": receivers.list(),
        })

    @routes.post("/api/device/{action}")
    async def device_do(request):
        action, body = request.match_info["action"], await request.json()
        if action == "brightness":
            save_setting(cfg, "brightness", device.set_brightness(body["percent"]))
            return ok(brightness=cfg["brightness"])
        if action == "dim":
            # The idle screen dims the display. The brightness to return to is stored before
            # dimming, so a reloaded page or a restart can never mistake the dimmed value for it.
            if device.brightness() is None:
                return ok()
            if not cfg["brightness"]:
                save_setting(cfg, "brightness", device.brightness())
            device.set_brightness(round(cfg["brightness"] * 0.3) if body["on"] else cfg["brightness"])
            return ok()
        if action == "wifi_powersave":
            await device.set_wifi_powersave(bool(body["on"]))
            return ok()
        if action == "power":
            await core.stop()
            await device.power(body["action"])
            return ok()
        if action == "update":
            return ok(changed=await device.update())
        if action == "receiver":
            await receivers.set(body["id"], bool(body["on"]))
            save_setting(cfg, "receivers_on", [r["id"] for r in receivers.list() if r["on"]])
            return ok()
        raise web.HTTPNotFound()

    @routes.get("/api/wifi")
    async def wifi_get(request):
        return web.json_response(await device.wifi_networks())

    @routes.post("/api/wifi")
    async def wifi_connect(request):
        body = await request.json()
        await device.wifi_connect(body["name"], body.get("password", ""))
        return ok()

    @routes.get("/api/tuner/onair")
    async def tuner_onair(request):
        """Shortwave broadcasters transmitting near a frequency right now."""
        if not await schedule.ready():
            return web.json_response([])
        khz = float(request.query["hz"]) / 1000
        return web.json_response(schedule.on_air(khz - 250, khz + 250)[:60])

    @routes.post("/api/tuner/scan")
    async def tuner_scan(request):
        body = await request.json()
        await tuner.scan(body["channels"], body["mode"], body.get("squelch", 6), body.get("waterfall", False))
        return ok()

    @routes.get("/api/alarm")
    async def alarm_get(request):
        return web.json_response({"enabled": alarm.data["enabled"], "time": alarm.data["time"],
                                  "fixed": (alarm.data["station"] or {}).get("title"),
                                  "last": (core.last or {}).get("title")})

    @routes.post("/api/alarm")
    async def alarm_set(request):
        body = await request.json()
        # "station": "last" follows what was heard last, "fix" pins the station heard last right now
        station = {"last": None, "fix": core.last}.get(body.get("station"), alarm.data["station"])
        alarm.set(body["enabled"], body["time"], station)
        core.update(alarm=alarm.data["time"] if alarm.data["enabled"] else None)
        return ok()

    @routes.get("/api/bluetooth")
    async def bluetooth_get(request):
        return web.json_response(await bt.status())

    @routes.post("/api/bluetooth/{action}")
    async def bluetooth_do(request):
        action, body = request.match_info["action"], await request.json()
        if action == "scan":
            await bt.scan()
        elif action == "connect":
            await bt.connect(body["mac"])
        elif action == "disconnect":
            await bt.disconnect(body["mac"])
        elif action == "visible":
            await bt.set_visible(bool(body["on"]))
        else:
            raise web.HTTPNotFound()
        return web.json_response(await bt.status())

    @routes.get("/api/settings")
    async def settings_get(request):
        return web.json_response({"fm_backend": cfg["fm_backend"], "tuner_backend": cfg["tuner_backend"],
                                  "fm_backend_used": fm.backend_id(), "tuner_backend_used": tuner.backend_id(),
                                  "fm_stereo": cfg["fm_stereo"],
                                  "remote": cfg["remote"], "addresses": addresses(cfg["port"]),
                                  "idle_content": cfg["idle_content"], "podcast_provider": cfg["podcast_provider"],
                                  "podcast_key": cfg["podcast_key"], "podcast_secret": cfg["podcast_secret"],
                                  "callsign": cfg["callsign"], "swl": cfg["swl"], "alerts": cfg["alerts"],
                                  "music_folder": str(music.root()),
                                  "version": __version__, "build": BUILD, "stream": network_audio.can_stream(),
                                  "backends": available_backends(),
                                  "engine_load": engine_load(), "engine_load_limit": ENGINE_LOAD_LIMIT})

    @routes.post("/api/settings")
    async def settings_set(request):
        body = await request.json()
        if body["key"] == "hidden_tiles":
            # the settings tile is the way back, so it cannot be hidden
            if not isinstance(body["value"], list) or not all(isinstance(t, str) and t != "settings" for t in body["value"]):
                raise ValueError("unknown setting")
            save_setting(cfg, "hidden_tiles", sorted(set(body["value"])))
            await core._broadcast()
            return ok()
        if body["key"] == "music_folder" and isinstance(body["value"], str):
            if body["value"] and not Path(body["value"]).expanduser().is_dir():
                raise ValueError("this folder cannot be opened")
            save_setting(cfg, "music_folder", str(Path(body["value"]).expanduser()) if body["value"] else None)
            return ok()
        if body["key"] == "alerts" and isinstance(body["value"], bool):
            save_setting(cfg, "alerts", body["value"])
            await alerts.look()
            return ok()
        if body["key"] == "callsign" and isinstance(body["value"], str):
            save_setting(cfg, "callsign", body["value"].strip().upper()[:15])
            return ok()
        if body["key"] in ("podcast_key", "podcast_secret") and isinstance(body["value"], str):
            save_setting(cfg, body["key"], body["value"].strip())
            return ok()
        allowed = {"fm_backend": CHOICES, "tuner_backend": CHOICES, "remote": (True, False),
                   "idle_content": ("clock", "gallery", "feed", "spots", "verse"), "podcast_provider": PROVIDERS, "swl": (True, False)}
        if body["value"] not in allowed.get(body["key"], ()):
            raise ValueError("unknown setting")
        if body["key"].endswith("_backend"):
            await core.stop()
        save_setting(cfg, body["key"], body["value"])
        if body["key"] == "idle_content":
            await core._broadcast()   # every open interface learns what its idle screen shows now
        return ok()

    async def name_location(request):
        """Look the place name up once per location and keep it with the settings."""
        language = request.headers.get("Accept-Language", "en")[:2]
        save_setting(cfg, "location_name", await place_name(cfg["location"], language))

    @routes.get("/api/location")
    async def location_get(request):
        return web.json_response({"location": cfg.get("location"), "name": cfg.get("location_name")})

    @routes.post("/api/location")
    async def location_set(request):
        body = await request.json()
        save_setting(cfg, "location", [round(float(body["lat"]), 4), round(float(body["lon"]), 4)])
        await name_location(request)
        asyncio.create_task(alerts.look())   # the warnings are those of the new place
        return ok()

    # Looking into folders and scaling photos takes its time on a slow disk or share: off the event loop.
    @routes.get("/api/gallery")
    async def gallery_get(request):
        return web.json_response(await asyncio.to_thread(gallery.info))

    @routes.post("/api/gallery")
    async def gallery_set(request):
        body = await request.json()
        save_setting(cfg, "gallery", {**gallery.settings, body["key"]: gallery.check(body["key"], body["value"])})
        await asyncio.to_thread(gallery.refresh, True)
        return ok()

    @routes.get("/api/gallery/folders")
    async def gallery_folders(request):
        return web.json_response(await asyncio.to_thread(subfolders, request.query.get("path") or "~"))

    @routes.get("/api/gallery/picture/{index}")
    async def gallery_picture(request):
        size = [int(request.query.get(side, 960)) for side in ("w", "h")]
        file = await asyncio.to_thread(gallery.picture, int(request.match_info["index"]), *size)
        if file is None:
            raise web.HTTPNotFound()
        return web.FileResponse(file)

    @routes.get("/api/weather")
    async def weather_get(request):
        forecast = await weather.get(cfg.get("location"))
        if not cfg.get("location_name"):   # location set before names existed, or the lookup failed
            await name_location(request)
        return web.json_response({**forecast, "place": cfg.get("location_name") or ""})

    @routes.get("/api/audio")
    async def audio_list(request):
        return web.json_response(await audio.sinks())

    @routes.post("/api/audio")
    async def audio_select(request):
        await audio.select((await request.json())["name"])
        await core.refresh_volume()
        return web.json_response(await audio.sinks())

    @routes.get("/api/webradio/stations")
    async def stations(request):
        return web.json_response(await webradio.search(request.query.get("q", "").strip()))

    @routes.get("/api/favorites")
    async def favorites_get(request):
        return web.json_response(core.favorites.items)

    @routes.post("/api/favorites")
    async def favorites_toggle(request):
        return web.json_response(core.favorites.toggle(await request.json()))

    @routes.post("/api/favorites/play")
    async def favorites_play(request):
        await core.play(await request.json())
        return ok()

    @routes.post("/api/favorites/clear")
    async def favorites_clear(request):
        return web.json_response(core.favorites.clear((await request.json()).get("kind")))

    @routes.post("/api/webradio/play")
    async def webradio_play(request):
        await webradio.play(await request.json())
        return ok()

    @routes.get("/api/dab/services")
    async def dab_services(request):
        return web.json_response({"services": dab.services, "scan": dab.scan_state, "slides": dab.slides()})

    @routes.get("/api/dab/slide/{sid}")
    async def dab_slide(request):
        sid = request.match_info["sid"]
        if sid not in dab.slides():
            raise web.HTTPNotFound()
        picture = (SLIDES / sid).read_bytes()
        kind = "image/png" if picture.startswith(b"\x89PNG") else "image/jpeg"
        return web.Response(body=picture, content_type=kind, headers={"Cache-Control": "no-cache"})

    @routes.post("/api/dab/scan")
    async def dab_scan(request):
        await dab.scan()
        return ok()

    @routes.post("/api/dab/play")
    async def dab_play(request):
        await dab.play((await request.json())["sid"])
        return ok()

    @routes.post("/api/fm/tune")
    async def fm_tune(request):
        body = await request.json()
        await fm.tune(body["mhz"], body.get("waterfall", False))
        return ok()

    @routes.post("/api/fm/stereo")
    async def fm_stereo(request):
        mode = (await request.json())["mode"]
        if mode not in ("auto", "stereo", "mono"):
            raise ValueError("unknown mode")
        save_setting(cfg, "fm_stereo", mode)
        if core.active is fm and fm.mhz is not None:
            await fm.tune(fm.mhz)
        return ok(mode=mode)

    @routes.get("/api/fm/names")
    async def fm_names(request):
        return web.json_response(fm.names)

    @routes.get("/api/fm/stations")
    async def fm_stations(request):
        return web.json_response(fm.stations)

    @routes.post("/api/fm/scan")
    async def fm_scan(request):
        await fm.scan()
        return web.json_response(fm.stations)

    @routes.get("/api/tuner/bands")
    async def tuner_bands(request):
        return web.json_response(BANDS)

    @routes.post("/api/tuner/tune")
    async def tuner_tune(request):
        body = await request.json()
        await tuner.tune(body["hz"], body["mode"], body.get("squelch", 0), body.get("zoom", 1),
                         body.get("label", ""), body.get("waterfall", False))
        return ok()

    @routes.post("/api/gain/reset")
    async def gain_reset(request):
        await core.stop()
        core.gains.forget()
        return ok()

    @routes.get("/stream/{source}")
    async def stream(request):
        source = {"fm": fm, "tuner": tuner}.get(request.match_info["source"])
        if source is None:
            raise web.HTTPNotFound()
        return await source.stream(request)

    @routes.post("/api/adsb/start")
    async def adsb_start(request):
        await adsb.start()
        return ok()

    @routes.get("/api/adsb/aircraft")
    async def adsb_aircraft(request):
        return web.json_response({"aircraft": adsb.list(), "location": cfg.get("location")})

    @routes.post("/api/sensors/start")
    async def sensors_start(request):
        await sensors.start()
        return ok()

    @routes.get("/api/sensors")
    async def sensors_get(request):
        return web.json_response({"sensors": sensors.list()})

    @routes.post("/api/ais/start")
    async def ais_start(request):
        await ais.start()
        return ok()

    @routes.get("/api/ais/ships")
    async def ais_ships(request):
        return web.json_response({"ships": ais.list(), "location": cfg.get("location")})

    @routes.get("/api/podcasts")
    async def podcasts_get(request):
        return web.json_response({"subscribed": podcasts.subscribed, "suggested": await podcasts.suggestions(),
                                  "provider": cfg["podcast_provider"]})

    @routes.get("/api/podcasts/search")
    async def podcasts_search(request):
        return web.json_response(await podcast_directory.search(cfg, request.query.get("q", "")))

    @routes.get("/api/podcasts/episodes")
    async def podcasts_episodes(request):
        return web.json_response(await podcasts.episodes(request.query["feed"]))

    @routes.post("/api/podcasts/{action}")
    async def podcasts_do(request):
        action, body = request.match_info["action"], await request.json()
        if action == "subscribe":
            podcasts.subscribe(body["podcast"], bool(body["on"]))
        elif action == "play":
            await podcasts.play(body)
        elif action == "seek":
            await podcasts.seek(float(body["seconds"]))
        else:
            raise web.HTTPNotFound()
        return ok()

    @routes.get("/api/feeds")
    async def feeds_get(request):
        return web.json_response({"feeds": feeds.feeds, "suggested": await feeds.suggestions(),
                                  "articles": await feeds.articles()})

    @routes.post("/api/feeds")
    async def feeds_set(request):
        body = await request.json()
        if body["action"] == "add":
            await feeds.add(body["url"])
        else:
            feeds.remove(body["url"])
        return ok()

    @routes.get("/api/propagation")
    async def propagation_get(request):
        return web.json_response(await space.get(cfg.get("location")))

    @routes.get("/api/verse")
    async def verse_get(request):
        language = request.headers.get("Accept-Language", "en")[:2].lower()
        return web.json_response(await asyncio.to_thread(verses.today, language))

    @routes.post("/api/verse")
    async def verse_set(request):
        body = await request.json()
        save_setting(cfg, "verse", {**verses.settings, body["key"]: verses.check(body["key"], body["value"])})
        return ok()

    @routes.post("/api/verse/import")
    async def verse_import(request):
        """A Losungen year file: uploaded from a browser, or lying in a folder of this computer."""
        if request.content_type.startswith("multipart/"):
            part = await (await request.multipart()).next()
            payload = await part.read(decode=False) if part is not None else b""
            return ok(years=await asyncio.to_thread(verses.keep, bytes(payload)))
        return ok(years=await asyncio.to_thread(verses.keep_from, (await request.json())["folder"]))

    @routes.get("/api/music")
    async def music_get(request):
        return web.json_response(await asyncio.to_thread(music.listing, request.query.get("path", "")))

    @routes.post("/api/music/{action}")
    async def music_do(request):
        action, body = request.match_info["action"], await request.json()
        if action == "play":
            await music.play(body.get("path", ""), body.get("file"), bool(body.get("shuffle")))
        elif action == "skip":
            await music.skip(int(body["step"]))
        else:
            raise web.HTTPNotFound()
        return ok()

    @routes.get("/api/audiobooks")
    async def audiobooks_get(request):
        return web.json_response({"shelf": shelf.books})

    @routes.get("/api/audiobooks/search")
    async def audiobooks_search(request):
        return web.json_response(await audiobooks.search(cfg["country"], request.query.get("q", "")))

    @routes.get("/api/audiobooks/chapters")
    async def audiobooks_chapters(request):
        book = await audiobooks.chapters(request.query["id"])
        for chapter in book["episodes"]:
            chapter["heard"] = round(podcasts.positions.get(chapter["id"], 0))
        return web.json_response(book)

    @routes.post("/api/audiobooks/shelf")
    async def audiobooks_shelf(request):
        body = await request.json()
        shelf.keep(body["book"], bool(body["on"]))
        return ok()

    @routes.get("/api/satellites")
    async def satellites_get(request):
        return web.json_response(await sky.get(cfg.get("location")))

    @routes.post("/api/aprs/start")
    async def aprs_start(request):
        await aprs.start()
        return ok()

    @routes.get("/api/aprs/stations")
    async def aprs_stations(request):
        return web.json_response({"stations": aprs.list(), "location": cfg.get("location"), "mhz": aprs.mhz()})

    @routes.get("/api/spots")
    async def spots_get(request):
        return web.json_response(await spots.get(request.query.get("kind", "dx")))

    @routes.get("/api/qso")
    async def qso_get(request):
        return web.json_response({"entries": log.list(), "callsign": cfg["callsign"], "swl": cfg["swl"],
                                  "bands": LOG_BANDS, "modes": LOG_MODES})

    @routes.post("/api/qso")
    async def qso_save(request):
        log.save(await request.json())
        return ok()

    @routes.post("/api/qso/{action}")
    async def qso_do(request):
        action, body = request.match_info["action"], await request.json()
        if action == "delete":
            log.delete(body["id"])
            return ok()
        if action == "export":
            return ok(path=log.export(body.get("kind")))
        raise web.HTTPNotFound()

    @routes.get("/api/qso/log.{kind}")
    async def qso_download(request):
        kind = "csv" if request.match_info["kind"] == "csv" else "adi"
        return web.Response(text=log.text(kind), content_type="text/csv" if kind == "csv" else "text/plain",
                            headers={"Content-Disposition": f'attachment; filename="qso-log.{kind}"'})

    @routes.get("/api/survey")
    async def survey_get(request):
        return web.json_response({"ranges": {k: [v[0] / 1e6, v[1] / 1e6, v[2] / 1e3] for k, v in survey.ranges().items()},
                                  "report": survey.report})

    @routes.post("/api/survey/{action}")
    async def survey_do(request):
        action, body = request.match_info["action"], await request.json()
        if action == "start":
            seconds = float(body.get("seconds", 0))
            if not 0 <= seconds <= 6 * 3600:
                raise ValueError("a survey runs for at most six hours")
            await survey.start(body["range"], seconds)
            return ok()
        if action == "save":
            return ok(path=survey.save())
        raise web.HTTPNotFound()

    @routes.get("/api/survey/report.txt")
    async def survey_download(request):
        if not survey.report:
            raise web.HTTPNotFound()
        return web.Response(text=as_text(survey.report), content_type="text/plain",
                            headers={"Content-Disposition": 'attachment; filename="radio-survey.txt"'})

    @routes.post("/api/timer")
    async def timer_set(request):
        seconds = float((await request.json())["seconds"])
        if not 0 <= seconds <= 24 * 3600:
            raise ValueError("a timer runs for at most a day")
        await timer.set(seconds)
        return ok()

    @routes.post("/api/apps/{id}/start")
    async def app_start(request):
        await apps.start(request.match_info["id"])
        return ok()

    app = web.Application(middlewares=[local_first, errors])

    async def revalidate(request, response):
        # Browsers guess how long a file without this header stays fresh; after an update
        # the kiosk then mixed an old page with a new script.
        response.headers.setdefault("Cache-Control", "no-cache")

    app.on_response_prepare.append(revalidate)
    app.add_routes(routes)
    app.router.add_static("/", WEB_DIR)

    async def on_startup(app):
        if cfg["brightness"] and device.brightness() is not None:
            device.set_brightness(cfg["brightness"])   # a restart while the idle screen was up left it dimmed
        await core.refresh_volume()
        app["audio_watch"] = asyncio.create_task(audio.watch(core.refresh_volume))
        app["alarm"] = asyncio.create_task(alarm.run())
        app["health"] = asyncio.create_task(core.watch_health())
        app["alerts"] = asyncio.create_task(alerts.run())
        await receivers.start_enabled()
        core.update(alarm=alarm.data["time"] if alarm.data["enabled"] else None)

    async def on_cleanup(app):
        app["audio_watch"].cancel()
        app["alarm"].cancel()
        app["health"].cancel()
        app["alerts"].cancel()
        await receivers.close()
        if bt.pairing:
            await bt.set_visible(False)
        await core.close()

    app.on_startup.append(on_startup)
    async def on_shutdown(app):
        # An open interface holds its connection for good; without closing it here a
        # restart waited a minute for the kiosk screen to let go.
        for socket in list(core.clients):
            await socket.close(code=1001)

    app.on_shutdown.append(on_shutdown)
    app.on_cleanup.append(on_cleanup)
    return app


def main():
    cfg = load_config()
    web.run_app(build(cfg), host=cfg["host"], port=cfg["port"])


if __name__ == "__main__":
    main()
