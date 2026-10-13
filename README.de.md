[English](README.md) · **Deutsch**

# RadioKiosk

Ein Radio fürs Küchenregal, ein digitaler Bilderrahmen und mit einem RTL-SDR-Stick ein Weltempfänger für den Funkplatz: RadioKiosk macht aus einem Linux-Rechner alle drei. Gebaut ist es für ein Touch-Display, es läuft aber genauso auf einem Laptop oder PC mit Maus und Tastatur.

[![Tests](https://github.com/TechnikWeber/RadioKiosk/actions/workflows/tests.yml/badge.svg)](https://github.com/TechnikWeber/RadioKiosk/actions/workflows/tests.yml)

![RadioKiosk auf einem Raspberry Pi mit 7-Zoll-Touch-Display, davor ein RTL-SDR-Stick](docs/screenshots/pi.jpg)

| | |
|---|---|
| ![Startbildschirm eines Küchenradios: nur Hören und Alltag](docs/screenshots/kitchen.png) | ![Ruhebildschirm als Bilderrahmen, mit Uhr, Wetter und dem, was läuft](docs/screenshots/idle.png) |
| ![Startbildschirm mit allen Kacheln, auch dem Funk-Hobby](docs/screenshots/home.png) | ![UKW mit Sendername und Wasserfall](docs/screenshots/fm.png) |
| ![Freier Empfänger auf dem 2-m-Amateurfunkband](docs/screenshots/receiver.png) | ![Live-Flugzeugkarte](docs/screenshots/aircraft.png) |

> Version 0.24: Alles hier Aufgeführte ist gebaut, aber nicht alles auf jeder Art von Hardware ausprobiert. Was ungetestet ist, steht in den Release-Notizen.

## Installation

```sh
curl -fsSL https://raw.githubusercontent.com/TechnikWeber/RadioKiosk/main/install.sh | bash
```

Läuft auf Fedora, Debian, Ubuntu und Raspberry Pi OS. Als normaler Benutzer ausführen; der Installer fragt für die Pakete nach dem Passwort, lädt RadioKiosk nach `~/.local/share/radiokiosk` und startet es als Hintergrunddienst. Danach **RadioKiosk** im Anwendungsmenü öffnen oder <http://localhost:8080> aufrufen.

Optionen, angehängt nach `bash -s --`:

| Option | Wirkung |
|---|---|
| `--kiosk` | öffnet die Oberfläche nach jeder Anmeldung im Vollbild und lässt das System seine Sicherheitsupdates selbst einspielen (`--no-security-updates` lässt das weg) |
| `--ham` | nimmt das Funk-Hobby dazu: Flugzeuge, Schiffe, Funksensoren, APRS, Satelliten und SDR++ werden installiert und ihre Kacheln gezeigt |
| `--with-sdrangel` | SDRangel als zweiter Experten-Empfänger |
| `--rotate=180` | dreht Bildschirm und Touch-Eingabe (auch `90`, `270`; Raspberry Pi OS) |

Ohne `--ham` kommt, was zum Hören und für den Alltag nötig ist. Die Hobby-Kacheln lassen sich später unter **Einstellungen › Kacheln auf dem Startbildschirm** einschalten; eine Kachel, deren Programm fehlt, bleibt weg.

### Raspberry Pi

**Raspberry Pi OS (64-bit) mit Desktop** aufspielen, ins Netz bringen und den Installer mit `--kiosk` ausführen. Nach dem nächsten Start öffnet der Pi RadioKiosk von selbst.

- **Bild steht auf dem Kopf:** Beim offiziellen 7-Zoll-Display ist das oft so; `--rotate=180` anhängen.
- **Strom:** Ein Pi mit Display und Stick braucht ein kräftiges Netzteil. RadioKiosk warnt, wenn der Pi zu wenig Spannung meldet.
- **Pi 3:** läuft, mit Grenzen. Die Oberfläche ist etwa zwei Minuten nach dem Einschalten da, der Wasserfall überfordert den Prozessor, und SDR++ passt nicht in den Speicher.

## Hardware

| Teil | Unterstützt | Getestet |
|---|---|---|
| Rechner | 64-Bit-Linux auf x86 oder ARM: Fedora, Debian, Ubuntu, Raspberry Pi OS | Fedora 44 auf einem Laptop; Raspberry Pi 3 B+ |
| Bildschirm | jeder, mit oder ohne Touch; ausgelegt für 800×480 aufwärts, auf großen Bildschirmen eine Stufe größer | offizielles 7-Zoll-Display; 480×320 bis 1920×1080 im Browser |
| SDR-Stick | optional. Jeder RTL2832U-Stick, den `librtlsdr` kennt (RTL-SDR Blog V3/V4, Nooelec). Airspy, HackRF und SDRplay werden nicht unterstützt | RTL-SDR Blog V4 |
| Ton | jeder Ausgang, den PipeWire oder PulseAudio anbietet: Klinke, USB, Bluetooth, HDMI | eingebauter Ton |

Ohne Stick läuft alles, was über das Internet kommt. Kurzwelle braucht einen Stick, der unter 24 MHz abstimmt (den V4, oder den V3 mit Direktabtastung), und eine lange Drahtantenne.

## Was es kann

Ein kleiner Python-Dienst steuert Player und Empfänger und liefert eine Weboberfläche aus, die ein Browser im Vollbild zeigt.

**Hören**

| Kachel | Was du bekommst |
|---|---|
| Webradio | Sendersuche, beliebte Sender, Logos |
| DAB+ | Suchlauf, Senderliste, Lauftext und die Bilder, die Sender mitschicken |
| UKW | Stereo, Sendernamen und Radiotext (RDS), Suchlauf, Wasserfall |
| Empfänger | freies Abstimmen in FM, AM und Seitenband mit Bandplan: Lang-, Mittel- und Kurzwelle, Amateurfunk, PMR446, Freenet, CB; auf den Rundfunkbändern steht, wer gerade sendet |
| Podcasts | Suche, Abos, Folgen; merkt sich, wie weit du gehört hast |
| Musik | eigene Dateien aus einem Ordner, vom USB-Stick oder Netzwerkordner |
| Hörbücher | gemeinfreie Hörbücher von LibriVox |
| Online-Medien | Titel, die yt-dlp findet und öffnet, über Suchwörter oder eine Adresse, als Ton gespielt; Suchen und Titel lassen sich merken |
| Bluetooth | einen Lautsprecher verbinden oder ein Handy über dieses Gerät spielen lassen |

**Alltag**

| Kachel | Was du bekommst |
|---|---|
| Nachrichten | RSS- und Atom-Feeds als Liste der neuesten Artikel |
| Wetter | aktuelles Wetter, Vorhersage für vier Tage, amtliche Warnungen |
| Kalender | die nächsten Termine von Kalendern, die woanders geführt werden, gelesen über ihre iCal-Adresse (Google, Apple, Abfallkalender, Schulferien) |
| Galerie | Diashow eines Ordners; Bilder lassen sich in der Oberfläche hinzufügen und löschen, auch vom Handy |
| Smart Home | Schalter, die beim Antippen eine Adresse aufrufen (ein Webhook von Home Assistant, eine Shelly-Steckdose), und Werte, die zeigen, was eine Adresse antwortet |
| Wecker, Timer | wecken mit einem Sender oder einem Ton; Küchentimer und Stoppuhr |
| Notizen, Erinnerungen | kurze Notizen; Erinnerungen für einen Tag, die bleiben, bis sie quittiert sind |

**Funk-Hobby** (mit `--ham`)

| Kachel | Was du bekommst |
|---|---|
| Flugzeuge, Schiffe | Live-Karten aus ADS-B und AIS |
| Funksensoren | Funk-Thermometer und Wetterstationen der Umgebung auf 433 MHz |
| APRS | Positionen, die Funkamateure auf 144,800 MHz senden, auf der Karte |
| Funkwetter | Sonnenwerte, Bandbedingungen und die MUF der nächsten Ionosonde |
| Funkaktivität | DX-Cluster und Parks on the Air; ein Tipp stimmt den Empfänger dorthin ab |
| Satelliten | Überflüge der ISS und anderer hörenswerter Satelliten |
| QSO-Log | Logbuch mit ADIF- und CSV-Export |
| Funk-Analyse | beobachtet einen Bereich über eine gewählte Zeit und berichtet, was auf Sendung war |
| SDR++ | das volle SDR-Programm für alles andere |

Einstellungen und Ausschalten sind zwei kleine Knöpfe am Ende der Favoritenzeile. Jeder Sender kann einen Stern bekommen, egal aus welcher Quelle; Favoriten starten mit einem Tipp vom Startbildschirm. Die Oberfläche ist standardmäßig englisch und lässt sich auf Deutsch umstellen.

### Bilderrahmen und Ruhebildschirm

Nach einer Weile ohne Berührung übernimmt der Ruhebildschirm. Er zeigt die Uhr auf Schwarz mit abgedunkeltem Display, oder eines oder mehrere davon im Wechsel: die Galerie hinter der Uhr, das Wetter mit den nächsten Tagen, die neuesten Nachrichten, den DX-Cluster, einen Bibelvers für den Tag. Wie lange jedes bleibt, lässt sich einzeln einstellen, etwa drei Minuten Bilder, dann eine Minute Wetter und eine Minute Nachrichten. Uhr, Datum, Wetter und das, was läuft, bleiben im Blick.

Als Bilderrahmen zeigt die Galerie jeden Ordner, den der Rechner lesen kann. Ein Bild, das den Bildschirm nicht füllt, bekommt statt schwarzer Ränder sich selbst unscharf als Hintergrund, oder es wird beschnitten und schwenkt langsam durch; der Wechsel zwischen Bildern blendet über, wischt, blättert oder zoomt. Bis du einen Ordner wählst, laufen Beispielbilder (gemeinfrei, siehe [demo-pictures/CREDITS.md](demo-pictures/CREDITS.md)).

Nachts lässt sich der Ruhebildschirm abdunkeln, auf die abgedunkelte Uhr reduzieren oder das Display ausschalten (**Einstellungen › Ruhebildschirm**). Damit ein vergessenes Radio nicht tagelang läuft, stoppt die Wiedergabe nach acht Stunden ohne Berührung von selbst (**Einstellungen › Wiedergabe**).

### Warnungen

Für den eingestellten Standort in Deutschland zeigt RadioKiosk die Warnungen des Wetterdienstes (über brightsky.dev) und des Bevölkerungsschutzes (NINA, von warnung.bund.de) als Zeile unter der Kopfzeile. Eine Warnung bleibt, bis jemand sie als gelesen markiert. Im Ruhebildschirm steht sie als Zeile; eine der beiden höchsten Stufen kommt einmal über den ganzen Ruhebildschirm. Ein Ton für die höchste Stufe lässt sich einschalten.

### Bibelvers und Herrnhuter Losungen

Der Vers stammt aus der kuratierten Liste des [Bibelvers-Widgets](https://github.com/TechnikWeber/bible-verse-widget) (gemeinfreie Übersetzungen) und ist in beiden am selben Tag derselbe.

Die Losungen sind nicht Teil von RadioKiosk: Sie sind für nichtkommerzielle Nutzung kostenlos, aber kein freier Inhalt. Lade die Jahresdatei (XML, ein ZIP) selbst von <https://www.losungen.de/digital/> und spiele sie unter **Einstellungen › Inhalte › Bibelvers** ein, vom Handy über die Fernbedienung oder aus einem Ordner oder vom USB-Stick. Das ist jedes Jahr zu wiederholen.

### Fernbedienung und andere Programme

Ist in den Einstellungen die Fernbedienung an, können Handys und Rechner im selben Netz die Oberfläche im Browser öffnen; andere Geräte können unter `http://<Adresse>:8080/live.mp3` auch mithören. Eine Hausautomation oder ein Skript kann RadioKiosk auf demselben Weg steuern, siehe [docs/api.de.md](docs/api.de.md). Es gibt keine Anmeldung, nutze das also nur in einem Netz, dem du vertraust.

### Gut zu wissen

- Den Stick kann immer nur ein Empfänger nutzen; der Dienst beendet den laufenden, bevor er den nächsten startet. Ein Stick, der sich am USB aufgehängt hat, wird neu gestartet.
- UKW und der freie Empfänger nutzen den eigenen Empfänger von RadioKiosk, geschrieben in Python mit NumPy. Der Wasserfall ist standardmäßig aus; in den Einstellungen lässt sich jeder der beiden auf das sparsamere `rtl_fm` umstellen.
- Podcasts, Musik und Online-Medien pausieren mit dem Knopf, der Radio stoppt; eine Sekunde gehalten, stoppt er sie ganz. Ein Aufnahmeknopf lässt sich in den Einstellungen einschalten; er speichert nach `Musik/RadioKiosk`.
- yt-dlp ist nicht Teil von RadioKiosk. Der Installer oder die Kachel holt es von seinem Projekt; eine so geholte Kopie wird wöchentlich erneuert.
- Das Abhören von Funkdiensten, die nicht für die Allgemeinheit bestimmt sind, ist in vielen Ländern eingeschränkt. Der Bandplan enthält nur Rundfunk, Amateurfunk und anmeldefreie Bänder.

## Aktualisieren

Unter **Einstellungen › Gerät** fragt „Nach Updates suchen“ bei GitHub nach einem neueren Release; RadioKiosk sieht auch einmal am Tag selbst nach und spielt ein neues Release, sofern nicht abgeschaltet, nachts ein, während nichts läuft.

Die neue Version wird in einen eigenen Ordner geholt und zuerst ausprobiert. Erst dann wird umgeschaltet, und antwortet die neue Version nicht innerhalb von zweieinhalb Minuten, schaltet ein Wächter zurück. Eingespielt werden nur Releases. Pakete des Betriebssystems bleiben unberührt; braucht eine Version ein neues, sagt sie das, und der Installer wird noch einmal ausgeführt.

## Aus dem Quelltext starten

```sh
git clone https://github.com/TechnikWeber/RadioKiosk.git
cd RadioKiosk
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m radiokiosk
.venv/bin/python -m unittest     # die Tests brauchen keinen SDR-Stick
```

Dafür braucht es die Programme, die der Installer einrichtet. Mit Stick darf der TV-Treiber des Kernels ihn nicht belegen:

```sh
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtlsdr.conf
```

## Einstellungsdatei

Fast alles wird in der Oberfläche eingestellt. Ein paar Dinge stehen nur in der optionalen Datei `~/.config/radiokiosk/config.json`:

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `host` | `0.0.0.0` | auf `127.0.0.1` setzen, um nie im Netz zu lauschen |
| `port` | `8080` | Port der Weboberfläche |
| `country` | `DE` | Land für die Liste beliebter Webradio-Sender |
| `gain` | `auto` | Tuner-Verstärkung: `auto` regelt beim Hören nach, eine Zahl in dB erzwingt sie |
| `apps` | SDR++, SDRangel | externe Programme, die als Kachel erscheinen |

## Lizenz

[MIT](LICENSE). Die Kurzwellen-Sendepläne stammen von [EiBi](http://www.eibispace.de/) von Eike Bierwirth, der sie kostenlos anbietet. Die mitgelieferte Kartenbibliothek Leaflet steht unter BSD-2-Clause, siehe `web/vendor/leaflet/LICENSE`.
