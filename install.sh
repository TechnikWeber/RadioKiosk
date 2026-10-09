#!/usr/bin/env bash
# RadioKiosk installer for Fedora and Debian-based systems (Debian, Ubuntu, Raspberry Pi OS).
#
#   curl -fsSL https://raw.githubusercontent.com/TechnikWeber/RadioKiosk/main/install.sh | bash
#
# Options (append after "bash -s --" when piping):
#   --kiosk           open the interface full screen after every login
#   --with-sdrangel   also install SDRangel as an additional expert receiver
#
# Run it as your normal user; it asks for sudo when it installs packages.
set -euo pipefail

REPO="https://github.com/TechnikWeber/RadioKiosk.git"
DIR="${RADIOKIOSK_DIR:-$HOME/.local/share/radiokiosk}"
WITH_SDRANGEL=0
KIOSK=0
for arg in "$@"; do
  case "$arg" in
    --kiosk) KIOSK=1 ;;
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
  OPTIONAL=(welle.io readsb sdrpp)
elif command -v dnf >/dev/null; then
  install() { sudo dnf install -y "$@"; }
  REQUIRED=(git python3 python3-aiohttp python3-numpy mpv rtl-sdr pulseaudio-utils bluez)
  OPTIONAL=(welle-io sdrpp dump1090)
else
  echo "Unsupported system: neither apt nor dnf found." >&2
  exit 1
fi
[ "$WITH_SDRANGEL" -eq 1 ] && OPTIONAL+=(sdrangel)

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
  if curl -fsSL -o "$TMP/$DEB" "https://github.com/AlexandreRouma/SDRPlusPlus/releases/download/nightly/$DEB" \
      && sudo apt-get install -y "$TMP/$DEB"; then
    MISSING=("${MISSING[@]/sdrpp}")
  fi
  rm -rf "$TMP"
fi

# The readsb package starts its own service, which would occupy the stick all the time.
if systemctl list-unit-files readsb.service >/dev/null 2>&1; then
  sudo systemctl disable --now readsb.service 2>/dev/null || true
fi

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
fi

say "Done"
echo "RadioKiosk is running. Open it from the application menu or at http://localhost:8080"
MISSING=(${MISSING[@]})   # drop entries emptied above
if [ "${#MISSING[@]}" -gt 0 ]; then
  warn "not available for your system: ${MISSING[*]}"
  echo "Their tiles stay disabled or hidden; everything else works."
fi
