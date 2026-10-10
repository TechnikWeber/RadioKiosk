#!/usr/bin/env bash
# RadioKiosk installer for Fedora and Debian-based systems (Debian, Ubuntu, Raspberry Pi OS).
#
#   curl -fsSL https://raw.githubusercontent.com/TechnikWeber/RadioKiosk/main/install.sh | bash
#
# Options (append after "bash -s --" when piping):
#   --kiosk           open the interface full screen after every login
#   --rotate=DEGREES  turn the screen by 90, 180 or 270 degrees (Raspberry Pi OS desktop)
#   --with-sdrangel   also install SDRangel as an additional expert receiver
#
# Run it as your normal user; it asks for sudo when it installs packages.
set -euo pipefail

REPO="https://github.com/TechnikWeber/RadioKiosk.git"
DIR="${RADIOKIOSK_DIR:-$HOME/.local/share/radiokiosk}"
WITH_SDRANGEL=0
KIOSK=0
ROTATE=""
for arg in "$@"; do
  case "$arg" in
    --kiosk) KIOSK=1 ;;
    --rotate=90|--rotate=180|--rotate=270) ROTATE="${arg#--rotate=}" ;;
    --with-sdrangel) WITH_SDRANGEL=1 ;;
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
  OPTIONAL=(welle.io readsb sdrpp shairport-sync)
  FFMPEG=ffmpeg
elif command -v dnf >/dev/null; then
  install() { sudo dnf install -y "$@"; }
  REQUIRED=(git python3 python3-aiohttp python3-numpy mpv rtl-sdr pulseaudio-utils bluez)
  OPTIONAL=(welle-io sdrpp dump1090 shairport-sync)
  FFMPEG=ffmpeg-free
else
  echo "Unsupported system: neither apt nor dnf found." >&2
  exit 1
fi
[ "$WITH_SDRANGEL" -eq 1 ] && OPTIONAL+=(sdrangel)
# ffmpeg encodes the network stream. Fedora offers two packages that exclude each
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
if ! command -v sdrpp >/dev/null && command -v apt-get >/dev/null; then
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
  git -C "$DIR" pull --ff-only
else
  mkdir -p "$(dirname "$DIR")"
  git clone --depth 1 "$REPO" "$DIR"
fi

say "Setting up the background service"
mkdir -p "$HOME/.config/systemd/user" "$HOME/.local/share/applications"
cat > "$HOME/.config/systemd/user/radiokiosk.service" <<UNIT
[Unit]
Description=RadioKiosk
After=pipewire-pulse.service pulseaudio.service

[Service]
WorkingDirectory=$DIR
ExecStart=/usr/bin/python3 -m radiokiosk
Restart=on-failure

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable radiokiosk.service
systemctl --user restart radiokiosk.service

cat > "$HOME/.local/share/applications/radiokiosk.desktop" <<ENTRY
[Desktop Entry]
Type=Application
Name=RadioKiosk
Comment=World receiver: web radio, DAB+, FM, shortwave and more
Exec=$DIR/radiokiosk-ui
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
