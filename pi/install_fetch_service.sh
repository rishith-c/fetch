#!/usr/bin/env bash
# Install FETCH as a Raspberry Pi systemd service.
# Use --dry-run first; the dry run makes no system changes.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
TEMPLATE="$SCRIPT_DIR/fetch.service.template"

SERIAL_PATH=""
MAP_PATH="$REPO_DIR/config/topo_map.demo.json"
START_ZONE=""
CAMERA_INDEX=0
PORT=8080
FETCH_HOSTNAME=fetch
DRY_RUN=0

usage(){
  printf '%s\n' \
    "Usage: $0 --serial /dev/serial/by-id/... --map /path/topo_map.json --start-zone ID [options]" \
    "Options: --camera N --port N --hostname NAME --dry-run"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --serial) SERIAL_PATH=${2:?missing serial path}; shift 2 ;;
    --map) MAP_PATH=${2:?missing map path}; shift 2 ;;
    --start-zone) START_ZONE=${2:?missing start zone}; shift 2 ;;
    --camera) CAMERA_INDEX=${2:?missing camera index}; shift 2 ;;
    --port) PORT=${2:?missing port}; shift 2 ;;
    --hostname) FETCH_HOSTNAME=${2:?missing hostname}; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

[ -n "$SERIAL_PATH" ] || { printf '%s\n' '--serial is required' >&2; exit 2; }
[ -n "$START_ZONE" ] || { printf '%s\n' '--start-zone is required' >&2; exit 2; }
case "$START_ZONE" in *[!0-9]*|'') printf '%s\n' 'start zone must be a nonnegative integer' >&2; exit 2;; esac
case "$CAMERA_INDEX" in *[!0-9]*|'') printf '%s\n' 'camera must be a nonnegative integer' >&2; exit 2;; esac
case "$PORT" in *[!0-9]*|'') printf '%s\n' 'port must be an integer' >&2; exit 2;; esac
[ "$PORT" -ge 1024 ] && [ "$PORT" -le 65535 ] || {
  printf '%s\n' 'port must be 1024-65535' >&2; exit 2;
}
[ -f "$MAP_PATH" ] || { printf 'Map does not exist: %s\n' "$MAP_PATH" >&2; exit 2; }

MAP_PATH=$(cd "$(dirname "$MAP_PATH")" && pwd)/$(basename "$MAP_PATH")
python3 "$REPO_DIR/pi/topo_nav.py" --map "$MAP_PATH" --check >/dev/null
python3 - "$MAP_PATH" "$START_ZONE" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    nodes = {int(key) for key in json.load(handle).get("adj", {})}
zone = int(sys.argv[2])
if zone not in nodes:
    raise SystemExit(f"start zone {zone} is not present in map nodes {sorted(nodes)}")
PY

if [ "$DRY_RUN" -eq 0 ] && [ ! -e "$SERIAL_PATH" ]; then
  printf 'Serial device does not exist: %s\n' "$SERIAL_PATH" >&2
  exit 2
fi

if [ -n "${SUDO_USER:-}" ]; then
  SERVICE_USER=$SUDO_USER
else
  SERVICE_USER=$(id -un)
fi

TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/fetch-service.XXXXXX")
cleanup(){ rm -rf "$TEMP_DIR"; }
trap cleanup EXIT
SERVICE_FILE="$TEMP_DIR/fetch.service"
ENV_FILE="$TEMP_DIR/fetch.env"

# Repository/user values are controlled local paths. Reject characters that
# would break the simple systemd template rather than trying clever escaping.
case "$REPO_DIR$SERVICE_USER" in *['&|']*) printf '%s\n' 'unsupported character in repository path or user' >&2; exit 2;; esac
sed -e "s|__FETCH_USER__|$SERVICE_USER|g" \
    -e "s|__FETCH_REPO__|$REPO_DIR|g" "$TEMPLATE" > "$SERVICE_FILE"
printf 'FETCH_MAP=%s\nFETCH_CAMERA=%s\nFETCH_SERIAL=%s\nFETCH_PORT=%s\nFETCH_START_ZONE=%s\n' \
  "$MAP_PATH" "$CAMERA_INDEX" "$SERIAL_PATH" "$PORT" "$START_ZONE" > "$ENV_FILE"

if [ "$DRY_RUN" -eq 1 ]; then
  printf '%s\n' '=== /etc/fetch.env ==='
  sed 's/^/  /' "$ENV_FILE"
  printf '%s\n' '=== /etc/systemd/system/fetch.service ==='
  sed 's/^/  /' "$SERVICE_FILE"
  printf 'DRY RUN PASS: map validates; start zone exists; no system files changed.\n'
  exit 0
fi

command -v systemctl >/dev/null 2>&1 || {
  printf '%s\n' 'systemctl is required; run this on Raspberry Pi OS' >&2; exit 2;
}
command -v apt-get >/dev/null 2>&1 || {
  printf '%s\n' 'apt-get is required; run this on Raspberry Pi OS' >&2; exit 2;
}

sudo apt-get update
sudo apt-get install -y python3-opencv python3-serial avahi-daemon
python3 -c 'import cv2, serial; assert hasattr(cv2, "aruco")'
sudo hostnamectl set-hostname "$FETCH_HOSTNAME"
sudo install -m 0644 "$ENV_FILE" /etc/fetch.env
sudo install -m 0644 "$SERVICE_FILE" /etc/systemd/system/fetch.service
sudo systemctl daemon-reload
sudo systemctl enable --now avahi-daemon.service fetch.service
sleep 3
sudo systemctl --no-pager --full status fetch.service
printf 'FETCH service installed. Test from the iPhone at http://%s.local:%s\n' \
  "$FETCH_HOSTNAME" "$PORT"
