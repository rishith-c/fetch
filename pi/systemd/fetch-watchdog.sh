#!/usr/bin/env bash
# Health watchdog. systemd already restarts a service that CRASHES; this
# catches the failures where nothing crashes and everything is still broken:
#
#   1. WiFi still associated, but the route out is gone. This is what a
#      captive portal timing out looks like. NetworkManager sees a healthy
#      link and does nothing, while Tailscale, Pi Connect and the tunnel all
#      go dark at once.
#   2. cloudflared running but not registered, so the URL resolves to nothing.
#   3. gui.py alive but wedged and no longer answering HTTP.
#
# Runs every 2 minutes from fetch-watchdog.timer. Everything it does is
# idempotent, so a spurious run costs nothing.
set -uo pipefail

log() { printf '%s %s\n' "$(date -Is)" "$*"; }

# ---------- 1. is the GUI answering? ----------
if ! curl -fsS -m 8 -o /dev/null http://localhost:8080/ 2>/dev/null; then
    log "GUI not answering, restarting"
    systemctl --user restart fetch-gui
    sleep 8
fi

# ---------- 2. is there a route out? ----------
# Two targets: one ping, one TCP. A network that blocks ICMP but passes 443
# is common, and bouncing WiFi on that would be a self-inflicted outage.
online() {
    ping -c1 -W3 1.1.1.1 >/dev/null 2>&1 && return 0
    curl -fsS -m 8 -o /dev/null https://cloudflare.com/cdn-cgi/trace 2>/dev/null && return 0
    return 1
}

if ! online; then
    log "no route out, bouncing wifi"
    dev=$(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="wifi"{print $1; exit}')
    if [ -n "${dev:-}" ]; then
        nmcli device disconnect "$dev" >/dev/null 2>&1
        sleep 3
        nmcli device connect "$dev" >/dev/null 2>&1
        sleep 15
    fi
    if online; then
        log "back online, restarting tunnel for a fresh URL"
        systemctl --user restart fetch-tunnel
    else
        log "still offline after bounce - likely a captive portal needing a browser"
    fi
    exit 0
fi

# ---------- 3. is the tunnel actually registered? ----------
# cloudflared prints its URL BEFORE the connection is up, so the presence of a
# URL proves nothing. Only a registered connection does.
if ! grep -aq "Registered tunnel connection" /home/varun/cf.log 2>/dev/null; then
    log "tunnel not registered, restarting"
    systemctl --user restart fetch-tunnel
fi
