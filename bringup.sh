#!/usr/bin/env bash
# FETCH bring-up: plug in the Pi, run this, get both working URLs.
#
# Everything on the Pi already auto-starts at boot (fetch-gui and fetch-tunnel
# are enabled systemd user services). What this handles is the Mac side, which
# is where the fragility actually lives:
#
#   1. tailscaled dies with the terminal, and its state used to sit in /tmp
#      where macOS wipes it - that logged us out mid-session. State now lives
#      in ~/.tailscale-state and is copied back in on every start.
#   2. Cloudflare quick-tunnel URLs are randomly regenerated on every reboot,
#      so the address has to be read off the Pi rather than remembered.
#
# Usage:  ./bringup.sh
set -uo pipefail

TS=/opt/homebrew/bin/tailscale
TSD=/opt/homebrew/bin/tailscaled
SOCK=/tmp/ts/tailscaled.sock
STATE_BACKUP=~/.tailscale-state/tailscaled.state
PI_IP=100.113.48.93

say() { printf '%s\n' "$*"; }

# ---------- 1. tailscale daemon ----------
if ! pgrep -f "[t]ailscaled --tun=userspace" >/dev/null; then
  say "starting tailscale daemon..."
  mkdir -p /tmp/ts
  [ -f "$STATE_BACKUP" ] && cp "$STATE_BACKUP" /tmp/ts/tailscaled.state
  nohup "$TSD" --tun=userspace-networking --socks5-server=localhost:1055 \
        --socket="$SOCK" --statedir=/tmp/ts >/tmp/ts/daemon.log 2>&1 &
  sleep 8
fi

if "$TS" --socket="$SOCK" status 2>&1 | grep -q "Logged out"; then
  say ""
  say "  Tailscale is logged out. Run this, open the link it prints, sign in:"
  say "    $TS --socket=$SOCK up"
  exit 1
fi

# Keep the good state safe for next time.
mkdir -p ~/.tailscale-state
cp /tmp/ts/tailscaled.state "$STATE_BACKUP" 2>/dev/null

# ---------- 2. wait for the Pi ----------
say "waiting for the Pi..."
for i in $(seq 1 20); do
  if ssh -o BatchMode=yes -o ConnectTimeout=6 pi "true" 2>/dev/null; then
    say "  Pi is up (${i}0s)"
    break
  fi
  [ "$i" = 20 ] && { say "  Pi never came up. Check power and the network."; exit 1; }
  sleep 8
done

# ---------- 3. make sure both services are running ----------
ssh -o BatchMode=yes -o ConnectTimeout=20 pi '
  for s in fetch-gui fetch-tunnel; do
    systemctl --user is-active "$s" >/dev/null 2>&1 || systemctl --user restart "$s"
  done
  sleep 6
' 2>/dev/null

# ---------- 4. read the current tunnel URL ----------
# Quick tunnels mint a new address per start, so the log is the only source of
# truth. Retry: cloudflared prints the URL a few seconds after the process
# starts, so an immediate read comes back empty on a cold boot.
URL=""
for i in $(seq 1 10); do
  # -a because cloudflared's log contains bytes grep calls binary, which
  # silently suppresses matches. And only trust a URL once the connection is
  # REGISTERED: cloudflared prints the address several seconds before it works.
  URL=$(ssh -o BatchMode=yes -o ConnectTimeout=15 pi \
        "grep -aq 'Registered tunnel connection' ~/cf.log 2>/dev/null && \
         grep -aoE 'https://[a-z0-9-]+\.trycloudflare\.com' ~/cf.log | tail -1" 2>/dev/null)
  [ -n "$URL" ] && break
  sleep 4
done

# ---------- 5. verify, do not assume ----------
say ""
if [ -z "$URL" ]; then
  say "  tunnel produced no URL - check: systemctl --user status fetch-tunnel"
  exit 1
fi

OP=$(curl -s -m 20 -o /dev/null -w '%{http_code}' "$URL/")
US=$(curl -s -m 20 -o /dev/null -w '%{http_code}' "$URL/user")
ST=$(curl -s -m 15 "$URL/state" 2>/dev/null)

say "  operator   $URL           [$OP]"
say "  user page  $URL/user      [$US]"
say ""
python3 - "$ST" <<'PY' 2>/dev/null
import json, sys
try:
    j = json.loads(sys.argv[1])
except Exception:
    print("  (no state - GUI may still be starting)"); raise SystemExit
c = j.get("cmap") or {}
print(f"  serial   {j.get('port')}")
print(f"  camera   {j.get('cam')}")
print(f"  sensors  {j.get('sensors')}")
print(f"  at       {c.get('current')}")
print(f"  nodes    {list((c.get('nodes') or {}).keys())}")
print(f"  edges    {len(c.get('edges') or [])}")
PY

[ "$OP" = "200" ] && [ "$US" = "200" ] && say "" && say "  both pages live." || {
  say ""; say "  one of the pages is not serving - see the codes above"; exit 1; }
