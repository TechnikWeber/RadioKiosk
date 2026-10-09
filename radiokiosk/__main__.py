"""HTTP API, WebSocket state feed and static web UI."""

import asyncio

from aiohttp import web

from . import audio, bluetooth
from .alarm import Alarm
from .config import WEB_DIR, load_config, save_setting
from .core import Core
from .sources.adsb import Adsb
from .sources.apps import Apps
from .sources.dab import Dab
from .sources.fm import Fm
from .sources.receiver import BACKENDS, available_backends
from .sources.tuner import BANDS, Tuner
from .sources.webradio import Webradio
from .weather import Weather, place_name


@web.middleware
async def errors(request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except (RuntimeError, KeyError, ValueError, OSError) as e:
        return web.json_response({"error": str(e) or type(e).__name__}, status=400)


def build(cfg):
    core = Core(cfg)
    webradio, dab, fm, tuner, apps = Webradio(core), Dab(core), Fm(core), Tuner(core), Apps(core)
    adsb = Adsb(core)
    weather = Weather()
    alarm = Alarm(core)
    bt = bluetooth.Bluetooth()
    core.players = {
        "webradio": lambda last: webradio.play(last["station"]),
        "dab": lambda last: dab.play(last["sid"]),
        "fm": lambda last: fm.tune(last["mhz"]),
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
        return web.json_response({"fm_backend": fm.backend_id(), "tuner_backend": tuner.backend_id(),
                                  "fm_stereo": cfg["fm_stereo"],
                                  "backends": available_backends()})

    @routes.post("/api/settings")
    async def settings_set(request):
        body = await request.json()
        if body["key"] not in ("fm_backend", "tuner_backend") or body["value"] not in BACKENDS:
            raise ValueError("unknown setting")
        await core.stop()
        save_setting(cfg, body["key"], body["value"])
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
        return ok()

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

    @routes.get("/api/webradio/favorites")
    async def favorites(request):
        return web.json_response(webradio.favorites)

    @routes.post("/api/webradio/favorites")
    async def favorite_toggle(request):
        return web.json_response(webradio.toggle_favorite(await request.json()))

    @routes.post("/api/webradio/play")
    async def webradio_play(request):
        await webradio.play(await request.json())
        return ok()

    @routes.get("/api/dab/services")
    async def dab_services(request):
        return web.json_response({"services": dab.services, "scan": dab.scan_state})

    @routes.post("/api/dab/scan")
    async def dab_scan(request):
        await dab.scan()
        return ok()

    @routes.post("/api/dab/play")
    async def dab_play(request):
        await dab.play((await request.json())["sid"])
        return ok()

    @routes.get("/api/fm/presets")
    async def fm_presets(request):
        return web.json_response(fm.presets)

    @routes.post("/api/fm/presets")
    async def fm_preset_toggle(request):
        return web.json_response(fm.toggle_preset((await request.json())["mhz"]))

    @routes.post("/api/fm/tune")
    async def fm_tune(request):
        await fm.tune((await request.json())["mhz"])
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

    @routes.get("/api/tuner/favorites")
    async def tuner_favorites(request):
        return web.json_response(tuner.favorites)

    @routes.post("/api/tuner/favorites")
    async def tuner_favorite_toggle(request):
        return web.json_response(tuner.toggle_favorite(await request.json()))

    @routes.post("/api/tuner/tune")
    async def tuner_tune(request):
        body = await request.json()
        await tuner.tune(body["hz"], body["mode"], body.get("squelch", 0), body.get("zoom", 1),
                         body.get("label", ""))
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

    @routes.post("/api/apps/{id}/start")
    async def app_start(request):
        await apps.start(request.match_info["id"])
        return ok()

    app = web.Application(middlewares=[errors])
    app.add_routes(routes)
    app.router.add_static("/", WEB_DIR)

    async def on_startup(app):
        await core.refresh_volume()
        app["audio_watch"] = asyncio.create_task(audio.watch(core.refresh_volume))
        app["alarm"] = asyncio.create_task(alarm.run())
        core.update(alarm=alarm.data["time"] if alarm.data["enabled"] else None)

    async def on_cleanup(app):
        app["audio_watch"].cancel()
        app["alarm"].cancel()
        if bt.pairing:
            await bt.set_visible(False)
        await core.close()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def main():
    cfg = load_config()
    web.run_app(build(cfg), host=cfg["host"], port=cfg["port"])


if __name__ == "__main__":
    main()
