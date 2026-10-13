#!/usr/bin/env bash
# RadioKiosk installer for Fedora and Debian-based systems (Debian, Ubuntu, Raspberry Pi OS).
#
#   curl -fsSL https://raw.githubusercontent.com/TechnikWeber/RadioKiosk/main/install.sh | bash
#
# Options (append after "bash -s --" when piping):
#   --kiosk           open the interface full screen after every login
#   --rotate=DEGREES  turn the screen by 90, 180 or 270 degrees (Raspberry Pi OS desktop)
#   --ham             also install the programs of the radio hobby (aircraft, ships, radio sensors,
#                     APRS, satellites, SDR++) and show their tiles
#   --with-sdrangel   also install SDRangel as an additional expert receiver (with --ham)
#   --security-updates     let the system install its security updates by itself (the default with --kiosk)
#   --no-security-updates  leave the system's updates alone, also with --kiosk
#
# Run it as your normal user; it asks for sudo when it installs packages.
set -euo pipefail

REPO="https://github.com/TechnikWeber/RadioKiosk.git"
DIR="${RADIOKIOSK_DIR:-$HOME/.local/share/radiokiosk}"
WITH_SDRANGEL=0
KIOSK=0
ROTATE=""
SECURITY=""
HAM=0
FRESH=1
[ -d "$DIR/.git" ] && FRESH=0
for arg in "$@"; do
  case "$arg" in
    --kiosk) KIOSK=1 ;;
    --rotate=90|--rotate=180|--rotate=270) ROTATE="${arg#--rotate=}" ;;
    --ham) HAM=1 ;;
    --with-sdrangel) WITH_SDRANGEL=1; HAM=1 ;;
    --security-updates) SECURITY=1 ;;
    --no-security-updates) SECURITY=0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33mWarning: %s\033[0m\n' "$*" >&2; }

if [ "$(id -u)" -eq 0 ]; then
  echo "Please run this as your normal user, not as root." >&2
  exit 1
fi

# Package names differ between the distribution families. The required set must
# install; optional programs only add tiles and may be missing from a repository.
if command -v apt-get >/dev/null; then
  install() { sudo apt-get install -y "$@"; }
  sudo apt-get update
  REQUIRED=(git python3 python3-aiohttp python3-numpy mpv rtl-sdr pulseaudio-utils bluez)
  OPTIONAL=(welle.io shairport-sync python3-pil)
  HOBBY=(readsb sdrpp rtl-433 rtl-ais python3-sgp4 direwolf)
  FFMPEG=ffmpeg
elif command -v dnf >/dev/null; then
  install() { sudo dnf install -y "$@"; }
  REQUIRED=(git python3 python3-aiohttp python3-numpy mpv rtl-sdr pulseaudio-utils bluez)
  OPTIONAL=(welle-io shairport-sync python3-pillow)
  HOBBY=(sdrpp dump1090 rtl-433 python3-sgp4 direwolf)
  FFMPEG=ffmpeg-free
else
  echo "Unsupported system: neither apt nor dnf found." >&2
  exit 1
fi
# Listening and everyday use come without asking; the radio hobby is for those who ask for it.
[ "$HAM" -eq 1 ] && OPTIONAL+=("${HOBBY[@]}")
[ "$WITH_SDRANGEL" -eq 1 ] && OPTIONAL+=(sdrangel)
# ffmpeg encodes the network stream and makes the gallery's clips out of videos. Fedora offers two packages that exclude each
# other, so only install one where none is present.
command -v ffmpeg >/dev/null || OPTIONAL+=("$FFMPEG")

say "Installing required packages"
install "${REQUIRED[@]}"

say "Installing optional receivers"
MISSING=()
for package in "${OPTIONAL[@]}"; do
  install "$package" || MISSING+=("$package")
done

# Debian and Ubuntu do not package SDR++; its project publishes .deb files per release.
if [ "$HAM" -eq 1 ] && ! command -v sdrpp >/dev/null && command -v apt-get >/dev/null; then
  . /etc/os-release
  case "$(dpkg --print-architecture)" in arm64) ARCH=aarch64 ;; *) ARCH="$(dpkg --print-architecture)" ;; esac
  DEB="sdrpp_${ID}_${VERSION_CODENAME}_${ARCH}.deb"
  TMP="$(mktemp -d)"
  if curl -fsSL --retry 5 --retry-all-errors --retry-delay 3 -o "$TMP/$DEB" "https://github.com/AlexandreRouma/SDRPlusPlus/releases/download/nightly/$DEB" \
      && sudo apt-get install -y "$TMP/$DEB"; then
    MISSING=("${MISSING[@]/sdrpp}")
  fi
  rm -rf "$TMP"
fi

# The readsb package starts its own service, which would occupy the stick all the time.
# shairport-sync's own service would play past RadioKiosk's audio output; RadioKiosk
# starts both itself when they are wanted.
for unit in readsb.service shairport-sync.service; do
  if systemctl list-unit-files "$unit" >/dev/null 2>&1; then
    sudo systemctl disable --now "$unit" 2>/dev/null || true
  fi
done

say "Keeping the kernel's TV driver away from the SDR stick"
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtlsdr.conf >/dev/null
sudo modprobe -r dvb_usb_rtl28xxu 2>/dev/null || true

say "Fetching RadioKiosk into $DIR"
if [ -d "$DIR/.git" ]; then
  # an installation on a release is brought up to date by its own update button
  if git -C "$DIR" symbolic-ref -q HEAD >/dev/null; then
    git -C "$DIR" pull --ff-only
  fi
else
  mkdir -p "$(dirname "$DIR")"
  # the newest release rather than whatever is being worked on; without any release, the branch
  LATEST="$(git ls-remote --tags --refs --sort=-v:refname "$REPO" 'v*' 2>/dev/null | head -n 1 | sed 's|.*refs/tags/||')"
  git clone --depth 1 ${LATEST:+--branch "$LATEST"} "$REPO" "$DIR"
fi
# The service starts from a link, not from the folder itself: an update fetches the new
# version into a folder of its own and turns the link, and back if the version does not start.
CURRENT="$DIR-current"
[ -e "$CURRENT" ] || ln -s "$DIR" "$CURRENT"

# The tiles of the radio hobby show with --ham. Without it they are hidden on a new installation only:
# an existing one keeps what it shows, and the settings can change it either way.
SETTINGS="${XDG_CONFIG_HOME:-$HOME/.config}/radiokiosk/config.json"
if [ "$HAM" -eq 1 ] || [ "$FRESH" -eq 1 ]; then
  mkdir -p "$(dirname "$SETTINGS")"
  python3 - "$SETTINGS" "$HAM" <<'PY'
import json, sys
path, ham = sys.argv[1], sys.argv[2] == "1"
try:
    settings = json.load(open(path))
except (OSError, ValueError):
    settings = {}
if ham or "ham" not in settings:
    settings["ham"] = ham
    json.dump(settings, open(path, "w"), indent=1)
PY
fi

say "Setting up the background service"
mkdir -p "$HOME/.config/systemd/user" "$HOME/.local/share/applications"
cat > "$HOME/.config/systemd/user/radiokiosk.service" <<UNIT
[Unit]
Description=RadioKiosk
After=pipewire-pulse.service pulseaudio.service

[Service]
WorkingDirectory=$CURRENT
ExecStart=/usr/bin/python3 -m radiokiosk
Restart=on-failure

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable radiokiosk.service
systemctl --user restart radiokiosk.service

# The Online media tile works through yt-dlp. The packaged one is usually too old for the sites
# it reads, so the project's own single file goes into RadioKiosk's folder, where the settings
# can renew it and RadioKiosk renews it once a week.
YTDLP="${XDG_CONFIG_HOME:-$HOME/.config}/radiokiosk/bin/yt-dlp"
if [ ! -e "$YTDLP" ]; then
  say "Fetching yt-dlp for the Online media tile"
  mkdir -p "$(dirname "$YTDLP")"
  if curl -fsSL -o "$YTDLP.part" https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
      && python3 "$YTDLP.part" --version >/dev/null 2>&1; then
    chmod +x "$YTDLP.part" && mv "$YTDLP.part" "$YTDLP"
  else
    rm -f "$YTDLP.part"
    warn "yt-dlp could not be fetched; the Online media tile offers to fetch it later."
  fi
fi

# A device that stands somewhere as a radio is not looked after like a desktop computer, so with
# --kiosk the system installs its security updates by itself: only those, and without restarting.
# RadioKiosk itself is updated by its own update button and at night.
[ -z "$SECURITY" ] && SECURITY="$KIOSK"
if [ "$SECURITY" -eq 1 ]; then
  say "Letting the system install its security updates by itself"
  if command -v apt-get >/dev/null; then
    # Debian's own setup of this package takes security updates only
    if install unattended-upgrades; then
      printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' \
        | sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null
    else
      warn "unattended-upgrades could not be installed; security updates stay manual."
    fi
  else
    if install dnf5-plugin-automatic 2>/dev/null || install dnf-automatic; then
      if [ ! -e /etc/dnf/automatic.conf ]; then
        printf '[commands]\nupgrade_type = security\napply_updates = yes\nreboot = never\n' \
          | sudo tee /etc/dnf/automatic.conf >/dev/null
      else
        warn "/etc/dnf/automatic.conf exists already and was left as it is."
      fi
      sudo systemctl enable --now dnf5-automatic.timer 2>/dev/null || sudo systemctl enable --now dnf-automatic.timer \
        || warn "the timer for automatic updates could not be switched on."
    else
      warn "dnf-automatic could not be installed; security updates stay manual."
    fi
  fi
fi

# Date, time and time zone can be corrected in the settings. The system asks polkit before it
# lets anybody touch the clock; this rule answers yes for the user the service runs as.
if [ -d /etc/polkit-1/rules.d ]; then
  say "Letting RadioKiosk set date, time and time zone"
  sudo tee /etc/polkit-1/rules.d/49-radiokiosk-clock.rules >/dev/null <<RULE
// RadioKiosk: its settings can correct date, time and time zone of this computer.
polkit.addRule(function(action, subject) {
  if (action.id.indexOf("org.freedesktop.timedate1.") === 0 && subject.user === "$USER") {
    return polkit.Result.YES;
  }
});
RULE
fi

cat > "$HOME/.local/share/applications/radiokiosk.desktop" <<ENTRY
[Desktop Entry]
Type=Application
Name=RadioKiosk
Comment=World receiver: web radio, DAB+, FM, shortwave and more
Exec=$CURRENT/radiokiosk-ui
Icon=audio-radio
Categories=AudioVideo;Audio;
ENTRY

if [ "$KIOSK" -eq 1 ]; then
  say "Opening the interface after every login"
  mkdir -p "$HOME/.config/autostart"
  cp "$HOME/.local/share/applications/radiokiosk.desktop" "$HOME/.config/autostart/radiokiosk.desktop"
  # Raspberry Pi OS hands touches to programs as mouse clicks. A finger dragged over a
  # list then selects instead of scrolling, so let the desktop (labwc) pass real touches.
  LABWC="$HOME/.config/labwc/rc.xml"
  if [ -f "$LABWC" ] && grep -q 'mouseEmulation="yes"' "$LABWC"; then
    cp "$LABWC" "$LABWC.before-radiokiosk"
    sed -i 's/mouseEmulation="yes"/mouseEmulation="no"/' "$LABWC"
    pkill -HUP -x labwc || true   # reads its settings again
  fi
fi

# Screens built into a case are often mounted upside down or on their side. The
# kernel command line carries the orientation: the boot screen follows it and so
# does the Raspberry Pi OS desktop (labwc), which must then not turn the picture a
# second time. Touch input does not follow the kernel, a udev rule turns it.
# Other desktops have their own display settings, which this script leaves alone.
if [ -n "$ROTATE" ]; then
  say "Turning the screen by $ROTATE degrees"
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  if [ -z "${WAYLAND_DISPLAY:-}" ]; then   # started over SSH: use the desktop session that is running
    for socket in "$XDG_RUNTIME_DIR"/wayland-[0-9]; do
      [ -S "$socket" ] && export WAYLAND_DISPLAY="$(basename "$socket")"
    done
  fi
  OUTPUT="$(wlr-randr 2>/dev/null | awk 'NR==1 {print $1}')" || true
  CMDLINE=/boot/firmware/cmdline.txt
  if [ -n "$OUTPUT" ] && [ -f "$CMDLINE" ]; then
    case "$ROTATE" in
      180) ORIENTATION=upside_down;   MATRIX="-1 0 1 0 -1 1" ;;
      90)  ORIENTATION=right_side_up; MATRIX="0 -1 1 1 0 0" ;;
      *)   ORIENTATION=left_side_up;  MATRIX="0 1 0 -1 0 1" ;;
    esac
    [ -f "$CMDLINE.before-radiokiosk" ] || sudo cp "$CMDLINE" "$CMDLINE.before-radiokiosk"
    sudo sed -i "1 s/ video=$OUTPUT:panel_orientation=[a-z_]*//; 1 s/\$/ video=$OUTPUT:panel_orientation=$ORIENTATION/" "$CMDLINE"
    printf '%s\n' "# RadioKiosk: the screen is turned by $ROTATE degrees, turn the touch input with it" \
      "ENV{ID_INPUT_TOUCHSCREEN}==\"1\", ENV{LIBINPUT_CALIBRATION_MATRIX}=\"$MATRIX\"" |
      sudo tee /etc/udev/rules.d/99-radiokiosk-touch.rules >/dev/null
    # The mouse pointer is drawn by the graphics chip, on a layer that does not turn with the
    # panel: on a turned screen it stands on its head. Drawn by the desktop instead, it is right.
    LABWC_ENV="$HOME/.config/labwc/environment"
    if [ -d "$HOME/.config/labwc" ] && ! grep -q "^WLR_NO_HARDWARE_CURSORS=" "$LABWC_ENV" 2>/dev/null; then
      echo "WLR_NO_HARDWARE_CURSORS=1" >> "$LABWC_ENV"
    fi
    # A transform in the desktop's own layout would add to the kernel's.
    KANSHI="$HOME/.config/kanshi/config"
    if [ -f "$KANSHI" ] && grep -q "transform" "$KANSHI"; then
      cp "$KANSHI" "$KANSHI.before-radiokiosk"
      sed -i 's/transform [a-z0-9-]*/transform normal/' "$KANSHI"
    fi
    if grep -q "video=$OUTPUT:panel_orientation=" /proc/cmdline; then
      wlr-randr --output "$OUTPUT" --transform normal
    else   # the kernel has not turned anything yet: turn the running desktop until the restart
      wlr-randr --output "$OUTPUT" --transform "$ROTATE"
    fi
    say "Restart the computer to finish turning the screen"
  else
    warn "could not turn the screen: this needs a running Raspberry Pi OS desktop (wlr-randr). Use your desktop's display settings instead."
  fi
fi

say "Done"
echo "RadioKiosk is running. Open it from the application menu or at http://localhost:8080"
MISSING=(${MISSING[@]})   # drop entries emptied above
if [ "${#MISSING[@]}" -gt 0 ]; then
  warn "not available for your system: ${MISSING[*]}"
  echo "Their tiles stay disabled or hidden; everything else works."
fi
