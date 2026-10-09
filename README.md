**English** · [Deutsch](README.de.md)

# RadioKiosk

Turns any Linux computer with a touchscreen and an RTL-SDR stick into a world receiver: web radio, DAB+, FM, shortwave, amateur radio and more in one touch interface.

> Early development. It runs on a Linux PC today; the kiosk setup for the Raspberry Pi (boot straight into the interface) is not finished yet.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/TechnikWeber/RadioKiosk/main/install.sh | bash
```

The installer works on Fedora and on Debian-based systems (Debian, Ubuntu, Raspberry Pi OS). Run it as your normal user; it asks for your password to install packages. It then:

1. installs the receivers and players RadioKiosk controls (`mpv`, `rtl-sdr`, `welle-cli`, SDR++, `dump1090`),
2. stops the kernel's TV driver from claiming the SDR stick,
3. downloads RadioKiosk to `~/.local/share/radiokiosk`,
4. starts it as a background service that also comes up after every login.

Afterwards open **RadioKiosk** from the application menu or go to <http://localhost:8080>. Run the same line again to update.

SDRangel is optional:

```sh
curl -fsSL https://raw.githubusercontent.com/TechnikWeber/RadioKiosk/main/install.sh | bash -s -- --with-sdrangel
```

Programs your distribution does not package are skipped; their tiles stay disabled or hidden and everything else works.

## Supported hardware

| Part | Supported | Tested |
|---|---|---|
| Computer | 64-bit Linux on x86 or ARM with Fedora, Debian, Ubuntu or Raspberry Pi OS | Fedora 44 on an x86 laptop |
| Raspberry Pi | Pi 4 and Pi 5 are the target; a Pi 3 should manage web radio, DAB+ and FM | not yet |
| SDR stick | RTL-SDR Blog V4 and V3, other RTL2832U sticks | RTL-SDR Blog V4 |
| Display | any; the interface is built for touch from 800×480 upwards | 800×480 layout in a browser |
| Audio | every output PipeWire or PulseAudio offers: headphone jack, USB, Bluetooth, HDMI | built-in audio |

Shortwave needs a stick that can tune below 24 MHz: the V4 does it with its built-in upconverter, the V3 through direct sampling. Either way it needs a long wire antenna. Without a stick, web radio still works.

## What it does

A small Python service controls the receivers and serves a web interface that a browser shows full screen.

| Tile | What you get | Backend |
|---|---|---|
| Web radio | station search, popular stations, favorites | radio-browser.info, `mpv` |
| DAB+ | station scan, station list, scrolling text | `welle-cli`, `mpv` |
| FM | stereo, station names and radio text (RDS), band scan, presets, spectrum and waterfall | built-in receiver or `rtl_fm`, `rtl_power`, `mpv` |
| Receiver | free tuning in FM, AM and sideband with waterfall, squelch and a band plan: shortwave, amateur radio, PMR446, Freenet, CB | built-in receiver, `mpv` |
| Aircraft | live map of the aircraft around you (ADS-B) | `dump1090` or `readsb`, Leaflet, OpenStreetMap |
| Bluetooth | connect a Bluetooth speaker, or let a phone play through this device | `bluetoothctl`, PipeWire |
| Weather | current weather and a four-day forecast | Open-Meteo |
| SDR++ | the full SDR program for everything else | started as a normal program |
| Settings | audio output, sleep timer, alarm clock, idle screen, on-screen keyboard, location, receiver backend | PipeWire or PulseAudio |

Only one receiver can use the stick at a time, so the service stops the running one before starting the next. Tiles whose program or hardware is missing are disabled.

FM and the free receiver use RadioKiosk's own receiver, written in Python with NumPy: it demodulates, decodes RDS, draws the waterfall and retunes without restarting the stick. Under Settings you can switch each of the two to the classic `rtl_fm` program instead (mono, no waterfall, lighter on the processor) and compare.

The tuner gain adjusts itself while listening, because the stick's own automatic gain overdrives on a good antenna. The values are remembered per band; reset them under Settings after changing the antenna.

The alarm clock wakes with a fixed station or with the one heard last; if that does not start, it falls back to a tone. The computer has to be running for it.

After a while without a touch, an idle screen shows the time, date, weather and what is playing. The interface brings its own on-screen keyboard for the station search, because system keyboards differ from desktop to desktop; it appears on touch screens and can be switched off under Settings.

Listening to radio services that are not meant for the public is restricted in many countries. The band plan therefore only contains broadcast, amateur radio and licence-free bands.

## Run from source

```sh
git clone https://github.com/TechnikWeber/RadioKiosk.git
cd RadioKiosk
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m radiokiosk
```

This needs the same programs the installer sets up, and the kernel's DVB driver must not claim the stick:

```sh
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtlsdr.conf
```

## Settings

Optional file `~/.config/radiokiosk/config.json`:

| Key | Default | Meaning |
|---|---|---|
| `host` | `127.0.0.1` | `0.0.0.0` allows control from other devices on the network (no login) |
| `port` | `8080` | port of the web interface |
| `country` | `DE` | country code for the list of popular web radio stations |
| `location` | not set | `[latitude, longitude]` for the aircraft map and the weather; easier to set under Settings |
| `fm_backend`, `tuner_backend` | `engine` | receiver for the FM and Receiver tiles: `engine` (built-in) or `rtl_fm`; also under Settings |
| `fm_stereo` | `auto` | FM sound: `auto` (stereo only on a strong signal), `stereo` or `mono`; also a button in the FM view |
| `gain` | `auto` | tuner gain: `auto` adjusts it while listening, a number in dB forces it |
| `apps` | SDR++, SDRangel | external programs shown as tiles |

## License

[MIT](LICENSE). The bundled map library Leaflet is BSD-2-Clause licensed, see `web/vendor/leaflet/LICENSE`.
