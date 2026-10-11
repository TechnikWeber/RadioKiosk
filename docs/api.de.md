# RadioKiosk von außen steuern

[English](api.md)

RadioKiosk wird über eine kleine Schnittstelle per HTTP bedient, dieselbe, die sein eigenes Display benutzt. Eine Hausautomation (Home Assistant, ioBroker, Node-RED), ein Skript oder ein Taster an der Wand kann sie ebenso nutzen: das Radio stoppen, wenn die Haustür zufällt, morgens einen Sender starten, leiser stellen, wenn das Telefon klingelt.

## Zugang

- Adresse: `http://<Adresse des Geräts>:8080`, zum Beispiel `http://radio.local:8080`.
- Vom Gerät selbst geht es immer. Von anderen Geräten geht es, sobald **Einstellungen › Fernbedienung** an ist, und nur aus demselben privaten Netz.
- Es gibt keine Anmeldung und keinen Schlüssel. Nutze es nur in einem Netz, dem du vertraust.
- Aufrufe, die etwas ändern, sind `POST` mit einem JSON-Inhalt und der Kopfzeile `Content-Type: application/json`. Sie antworten `{"ok": true}`, oder `{"error": "…"}` mit Status 400.

Die Schnittstelle gehört zum eigenen Display von RadioKiosk und wächst mit ihm. Die Aufrufe auf dieser Seite sollen bleiben; es gibt weitere, die sich ändern können.

## Was gerade läuft

`GET /api/state` antwortet mit dem Zustand als JSON. Die Felder, die von außen nützen:

| Feld | Bedeutung |
|---|---|
| `source` | was spielt: `webradio`, `dab`, `fm`, `tuner`, `podcast`, `music`, `media` oder `null` |
| `status` | `idle`, `loading`, `playing`, `paused` oder `error` |
| `title`, `text` | Sender oder Titel, und die Zeile darunter (das Lied, wenn der Sender es nennt) |
| `volume`, `muted` | Lautstärke in Prozent, und ob der Ton stumm ist |
| `alarm` | die Weckzeit, solange der Wecker an ist |
| `sleep_until` | wann der Sleep-Timer stoppt (Unix-Zeit), oder `null` |

`GET /ws` ist ein WebSocket, der denselben Zustand sofort und bei jeder Änderung wieder schickt, für alle, die lieber zuhören als fragen.

## Wiedergabe

| Aufruf | Inhalt | Wirkung |
|---|---|---|
| `POST /api/stop` | `{}` | stoppt, was läuft |
| `POST /api/pause` | `{"on": true}` | pausiert Podcast, Musik oder Online-Medien; `false` lässt weiterlaufen. Radio lässt sich nicht pausieren |
| `POST /api/volume` | `{"value": 40}` | setzt die Lautstärke, 0 bis 100; hebt auch eine Stummschaltung auf |
| `POST /api/mute` | `{"on": true}` | schaltet stumm, `false` holt den Ton mit der alten Lautstärke zurück |
| `POST /api/sleep` | `{"minutes": 30}` | stoppt die Wiedergabe nach so vielen Minuten; `0` schaltet den Sleep-Timer aus |
| `POST /api/timer` | `{"seconds": 300}` | startet den Küchentimer; `0` löscht ihn |

## Einen Sender starten

`GET /api/favorites` listet die Favoriten. Ein Eintrag wird unverändert zurückgeschickt, um ihn zu starten:

```sh
curl -s http://radio.local:8080/api/favorites
curl -X POST -H 'Content-Type: application/json' \
  -d '{"kind": "webradio", "title": "SWR3", "station": {"id": "swr3", "name": "SWR3", "url": "https://liveradio.swr.de/sw282p3/swr3/play.mp3"}}' \
  http://radio.local:8080/api/favorites/play
```

Jede Stream-Adresse spielt auch, ohne Favorit zu sein:

```sh
curl -X POST -H 'Content-Type: application/json' \
  -d '{"id": "mein-stream", "name": "Mein Stream", "url": "https://example.org/stream.mp3"}' \
  http://radio.local:8080/api/webradio/play
```

`GET /api/webradio/stations?q=<Wörter>` sucht im Senderverzeichnis; ein Eintrag der Antwort lässt sich unverändert an `/api/webradio/play` schicken.

## Das Gerät

| Aufruf | Inhalt | Wirkung |
|---|---|---|
| `POST /api/device/brightness` | `{"percent": 60}` | setzt die Helligkeit des Displays, wo sie sich setzen lässt |
| `POST /api/device/power` | `{"action": "poweroff"}` | fährt den Rechner herunter; `"reboot"` startet ihn neu |
| `POST /api/audio/test` | `{"side": "left"}` | ein kurzer Testton: `left`, `right` oder `both` |

## Beispiele für Home Assistant

In der `configuration.yaml`:

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

Die andere Richtung, vom Radio aus etwas im Haus schalten, ist die Kachel **Smart Home**: Ihre Schalter rufen eine Adresse auf, zum Beispiel einen Webhook von Home Assistant, und ihre Werte zeigen, was eine Adresse antwortet.
