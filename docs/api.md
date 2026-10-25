# Controlling RadioKiosk from outside

[Deutsch](api.de.md)

RadioKiosk is operated through a small interface over HTTP, the same one its own display uses. A home automation (Home Assistant, ioBroker, Node-RED), a script or a button on the wall can use it too: stop the radio when the door closes, start a station in the morning, lower the volume when the phone rings.

## Access

- Address: `http://<address of the device>:8080`, for example `http://radio.local:8080`.
- From the device itself it always works. From other devices it works once **Settings › Remote control** is on, and only from the same private network.
- There is no login and no key. Use it only in a network you trust.
- Requests that change something are `POST` with a JSON body and the header `Content-Type: application/json`. They answer `{"ok": true}`, or `{"error": "…"}` with status 400.

The interface belongs to RadioKiosk's own display and grows with it. The calls on this page are meant to stay; others exist and may change.

## What is playing

`GET /api/state` answers with the state as JSON. The fields of use from outside:

| Field | Meaning |
|---|---|
| `source` | what plays: `webradio`, `dab`, `fm`, `tuner`, `podcast`, `music`, `media`, or `null` |
| `status` | `idle`, `loading`, `playing`, `paused` or `error` |
| `title`, `text` | station or title, and the line below it (the song, where the station names it) |
| `volume`, `muted` | volume in per cent, and whether the sound is muted |
| `alarm` | the alarm time while the alarm is on |
| `sleep_until` | when the sleep timer stops playing (Unix time), or `null` |

`GET /ws` is a WebSocket that sends the same state at once and again on every change, for those who would rather listen than ask.

## Playing

| Call | Body | What it does |
|---|---|---|
| `POST /api/stop` | `{}` | stops what is playing |
| `POST /api/pause` | `{"on": true}` | pauses a podcast, music or online media; `false` goes on. Radio cannot pause |
| `POST /api/volume` | `{"value": 40}` | sets the volume, 0 to 100; also lifts a muting |
| `POST /api/mute` | `{"on": true}` | mutes, `false` brings the sound back at the old volume |
| `POST /api/sleep` | `{"minutes": 30}` | stops playing after so many minutes; `0` switches the sleep timer off |
| `POST /api/timer` | `{"seconds": 300}` | starts the kitchen timer; `0` clears it |

## Starting a station

`GET /api/favorites` lists the favourites. Each entry is sent back as it is to start it:

```sh
curl -s http://radio.local:8080/api/favorites
curl -X POST -H 'Content-Type: application/json' \
  -d '{"kind": "webradio", "title": "SWR3", "station": {"id": "swr3", "name": "SWR3", "url": "https://liveradio.swr.de/sw282p3/swr3/play.mp3"}}' \
  http://radio.local:8080/api/favorites/play
```

Any stream address plays without being a favourite:

```sh
curl -X POST -H 'Content-Type: application/json' \
  -d '{"id": "my-stream", "name": "My stream", "url": "https://example.org/stream.mp3"}' \
  http://radio.local:8080/api/webradio/play
```

`GET /api/webradio/stations?q=<words>` searches the station directory by name and genre; an entry of the answer can be sent to `/api/webradio/play` as it is. Without `q` it lists the most popular stations; `genre=<id>` (such as `pop`, `schlager`, `classical`, see `GENRES` in `radiokiosk/sources/webradio.py`) the most popular of a genre. `scope=country` keeps to the country set, `scope=language` to stations in the language given with `lang=de` or `lang=en`, without `scope` the whole world counts. Each answer holds up to 60 stations; `page=1`, `page=2` … bring the next ones.

## The device

| Call | Body | What it does |
|---|---|---|
| `POST /api/device/brightness` | `{"percent": 60}` | sets the brightness of the display, where it can be set |
| `POST /api/device/power` | `{"action": "poweroff"}` | shuts the computer down; `"reboot"` restarts it |
| `POST /api/audio/test` | `{"side": "left"}` | a short test tone: `left`, `right` or `both` |

## Examples for Home Assistant

In `configuration.yaml`:

```yaml
rest_command:
  radio_stop:
    url: http://radio.local:8080/api/stop
    method: post
    content_type: application/json
    payload: "{}"
  radio_volume:
    url: http://radio.local:8080/api/volume
    method: post
    content_type: application/json
    payload: '{"value": {{ volume }}}'

sensor:
  - platform: rest
    name: Radio
    resource: http://radio.local:8080/api/state
    value_template: "{{ value_json.title or 'off' }}"
    scan_interval: 30
```

The other direction, switching something in the home from the radio, is the **Smart home** tile: its switches call an address, a webhook of Home Assistant for instance, and its values show what an address answers.
