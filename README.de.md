[English](README.md) · **Deutsch**

# RadioKiosk

Macht aus jedem Linux-Rechner mit Touchscreen und RTL-SDR-Stick einen Weltempfänger: Webradio, DAB+, UKW, Kurzwelle, Amateurfunk und mehr in einer Touch-Oberfläche.

> Frühe Entwicklung. Es läuft heute auf einem Linux-PC; die Kiosk-Einrichtung für den Raspberry Pi (Start direkt in die Oberfläche) ist noch nicht fertig.

## Installation

```sh
curl -fsSL https://raw.githubusercontent.com/TechnikWeber/RadioKiosk/main/install.sh | bash
```

Der Installer läuft auf Fedora und auf Debian-basierten Systemen (Debian, Ubuntu, Raspberry Pi OS). Starte ihn als normaler Benutzer; er fragt nach deinem Passwort, um Pakete zu installieren. Danach erledigt er Folgendes:

1. Er installiert die Empfänger und Abspieler, die RadioKiosk steuert (`mpv`, `rtl-sdr`, `welle-cli`, SDR++, `dump1090`).
2. Er hindert den TV-Treiber des Kernels daran, den SDR-Stick zu belegen.
3. Er lädt RadioKiosk nach `~/.local/share/radiokiosk`.
4. Er startet es als Hintergrunddienst, der auch nach jeder Anmeldung wieder läuft.

Anschließend öffnest du **RadioKiosk** im Anwendungsmenü oder rufst <http://localhost:8080> auf. Zum Aktualisieren führst du dieselbe Zeile noch einmal aus.

SDRangel ist optional:

```sh
curl -fsSL https://raw.githubusercontent.com/TechnikWeber/RadioKiosk/main/install.sh | bash -s -- --with-sdrangel
```

Programme, die deine Distribution nicht als Paket anbietet, werden übersprungen; ihre Kacheln bleiben deaktiviert oder unsichtbar, alles andere funktioniert.

## Unterstützte Hardware

| Teil | Unterstützt | Getestet |
|---|---|---|
| Rechner | 64-bit-Linux auf x86 oder ARM mit Fedora, Debian, Ubuntu oder Raspberry Pi OS | Fedora 44 auf einem x86-Laptop |
| Raspberry Pi | Pi 4 und Pi 5 sind das Ziel; ein Pi 3 sollte Webradio, DAB+ und UKW schaffen | noch nicht |
| SDR-Stick | RTL-SDR Blog V4 und V3, andere RTL2832U-Sticks | RTL-SDR Blog V4 |
| Display | beliebig; die Oberfläche ist für Touch ab 800×480 gebaut | 800×480-Layout im Browser |
| Ton | jede Ausgabe, die PipeWire oder PulseAudio anbietet: Klinke, USB, Bluetooth, HDMI | eingebauter Ton |

Kurzwelle braucht einen Stick, der unter 24 MHz abstimmen kann: Der V4 macht das mit seinem eingebauten Umsetzer, der V3 über Direct Sampling. In beiden Fällen ist eine lange Drahtantenne nötig. Ohne Stick funktioniert weiterhin das Webradio.

## Was es kann

Ein kleiner Python-Dienst steuert die Empfänger und liefert eine Weboberfläche aus, die ein Browser im Vollbild zeigt.

| Kachel | Funktionen | Technik dahinter |
|---|---|---|
| Webradio | Sendersuche, beliebte Sender, Favoriten | radio-browser.info, `mpv` |
| DAB+ | Sendersuchlauf, Senderliste, Lauftext | `welle-cli`, `mpv` |
| UKW | Stereo, Sendernamen und Radiotext (RDS), Sendersuchlauf, Speicherplätze, Spektrum und Wasserfall | eingebauter Empfänger oder `rtl_fm`, `rtl_power`, `mpv` |
| Empfänger | freies Abstimmen in FM, AM und Seitenband mit Wasserfall, Rauschsperre und Bandplan: Kurzwelle, Amateurfunk, PMR446, Freenet, CB | eingebauter Empfänger, `mpv` |
| Flugzeuge | Live-Karte der Flugzeuge in deiner Umgebung (ADS-B) | `dump1090` oder `readsb`, Leaflet, OpenStreetMap |
| Bluetooth | Bluetooth-Lautsprecher verbinden oder ein Handy über dieses Gerät abspielen lassen | `bluetoothctl`, PipeWire |
| Wetter | aktuelles Wetter und Vorhersage für vier Tage | Open-Meteo |
| SDR++ | das vollwertige SDR-Programm für alles Weitere | startet als normales Programm |
| Einstellungen | Tonausgabe, Sleep-Timer, Wecker, Standort, Empfangsart | PipeWire oder PulseAudio |

Den Stick kann immer nur ein Empfänger nutzen, deshalb beendet der Dienst den laufenden, bevor er den nächsten startet. Kacheln, deren Programm oder Hardware fehlt, sind deaktiviert.

UKW und der freie Empfänger nutzen den eigenen Empfänger von RadioKiosk, geschrieben in Python mit NumPy: Er demoduliert, dekodiert RDS, zeichnet den Wasserfall und stimmt um, ohne den Stick neu zu starten. In den Einstellungen lässt sich jede der beiden Kacheln stattdessen auf das klassische Programm `rtl_fm` umstellen (Mono, kein Wasserfall, schont den Prozessor) und vergleichen.

Die Tuner-Verstärkung regelt sich beim Hören selbst nach, weil die Automatik des Sticks an einer guten Antenne übersteuert. Die Werte werden je Band gemerkt; nach einem Antennenwechsel setzt du sie in den Einstellungen zurück.

Der Wecker weckt mit dem zuletzt gehörten Sender; startet der nicht, ertönt ersatzweise ein Ton. Der Rechner muss dafür laufen.

Das Abhören von Funkdiensten, die nicht für die Allgemeinheit bestimmt sind, ist in vielen Ländern eingeschränkt. Der Bandplan enthält deshalb nur Rundfunk, Amateurfunk und anmeldefreie Bänder.

## Aus dem Quelltext starten

```sh
git clone https://github.com/TechnikWeber/RadioKiosk.git
cd RadioKiosk
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m radiokiosk
```

Dafür braucht es dieselben Programme, die der Installer einrichtet, und der DVB-Treiber des Kernels darf den Stick nicht belegen:

```sh
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtlsdr.conf
```

## Einstellungen

Optionale Datei `~/.config/radiokiosk/config.json`:

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `host` | `127.0.0.1` | `0.0.0.0` erlaubt die Bedienung von anderen Geräten im Netz (ohne Anmeldung) |
| `port` | `8080` | Port der Weboberfläche |
| `country` | `DE` | Ländercode für die Liste beliebter Webradio-Sender |
| `location` | nicht gesetzt | `[Breite, Länge]` für Flugzeug-Karte und Wetter; einfacher in den Einstellungen festzulegen |
| `fm_backend`, `tuner_backend` | `engine` | Empfänger für die Kacheln UKW und Empfänger: `engine` (eingebaut) oder `rtl_fm`; auch in den Einstellungen |
| `gain` | `auto` | Tuner-Verstärkung: `auto` regelt sie beim Hören nach, eine Zahl in dB erzwingt sie |
| `apps` | SDR++, SDRangel | externe Programme, die als Kachel erscheinen |

## Lizenz

[MIT](LICENSE). Die mitgelieferte Kartenbibliothek Leaflet steht unter der BSD-2-Clause-Lizenz, siehe `web/vendor/leaflet/LICENSE`.
