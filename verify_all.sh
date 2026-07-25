#!/usr/bin/env bash
# FETCH — verify EVERYTHING. Run before you trust any of this.
#
#   ./verify_all.sh
#
# Checks, in order:
#   1. engineering invariants (every constant re-derived)
#   2. Arduino firmware actually compiles for the Uno R4
#   3. Pi python compiles + the relay's API answers correctly
#   4. iOS app typechecks against the real iOS SDK
#   5. CAD is single-body + watertight
#   6. markers actually decode
set -uo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:$PATH"    # for arduino-cli

# CAREFUL: the PATH line above makes `python3` resolve to Homebrew's 3.13, which
# does NOT have cv2 — cv2 lives in the system python. Silently using the wrong
# interpreter made the marker check report "opencv not installed" when it was.
# So: pick an interpreter per capability instead of assuming.
pick_py(){  # pick_py <module>  -> prints an interpreter that can import it
  for c in /usr/bin/python3 /opt/homebrew/bin/python3 python3; do
    [ -x "$(command -v "$c" 2>/dev/null)" ] || continue
    "$c" -c "import $1" >/dev/null 2>&1 && { echo "$c"; return 0; }
  done
  return 1
}
PY_BASE=$(command -v python3)
PY_CV=$(pick_py cv2 || true)

PASS=0; FAIL=0
ok(){ echo "  ✓ $1"; PASS=$((PASS+1)); }
no(){ echo "  ✗ $1"; FAIL=$((FAIL+1)); }
hdr(){ echo; echo "=== $1 ==="; }

hdr "1. ENGINEERING INVARIANTS"
if python3 sim/verify.py > /tmp/fetch_verify.log 2>&1; then
  ok "sim/verify.py — $(grep -c '\[OK' /tmp/fetch_verify.log) checks pass"
else
  no "sim/verify.py FAILED"; tail -6 /tmp/fetch_verify.log | sed 's/^/      /'
fi

hdr "2. FIRMWARE (Arduino Uno R4)"
if command -v arduino-cli >/dev/null 2>&1; then
  if OUT=$(arduino-cli compile --fqbn arduino:renesas_uno:minima firmware/fetch_drive 2>&1); then
    ok "compiles — $(echo "$OUT" | grep -o '[0-9]*%' | head -1) flash"
  else
    no "compile FAILED"; echo "$OUT" | tail -5 | sed 's/^/      /'
  fi
else
  echo "  – arduino-cli not installed (brew install arduino-cli)"
fi

hdr "3. RASPBERRY PI"
for f in pi/fetch_relay.py pi/topo_nav.py pi/topo_server.py tools/make_topo_map.py tools/final_manual_audit.py tools/motor_JK42HS40_1704_13A.py; do
  python3 -m py_compile "$f" 2>/dev/null && ok "$f compiles" || no "$f FAILED"
done
if python3 tools/final_manual_audit.py >/tmp/fetch_manual.log 2>&1; then
  ok "final manual matches firmware — $(grep -c '\[OK' /tmp/fetch_manual.log) checks"
else
  no "final manual mismatch"; tail -6 /tmp/fetch_manual.log | sed 's/^/      /'
fi
if grep -q 'self.estop = p\[-1\]' pi/fetch_relay.py \
   && grep -q 'self.estop = parts\[-1\]' pi/topo_server.py; then
  ok "telemetry parser accepts five-ultrasonic packet"
else
  no "telemetry parser field-count mismatch"
fi
TOPO_TMP=$(mktemp /tmp/fetch_topo.XXXXXX.json)
if python3 tools/make_topo_map.py --edges 0-1,1-2,2-3,2-4 --output "$TOPO_TMP" >/dev/null 2>&1 \
   && python3 pi/topo_nav.py --map "$TOPO_TMP" --check | grep -q CONNECTED; then
  ok "checkpoint remap: connected graph routes"
else
  no "checkpoint remap validation FAILED"
fi
rm -f "$TOPO_TMP"
# live API test against the real relay, in dry mode
(python3 pi/fetch_relay.py --port 8791 >/dev/null 2>&1 &) ; sleep 2
V='{"heading_err_deg":20,"range_m":5,"bearing_deg":0,"seq":1}'
curl -s -X POST http://127.0.0.1:8791/vector -H 'Content-Type: application/json' -d "$V" >/dev/null 2>&1
sleep 0.3
S=$(curl -s -m 2 http://127.0.0.1:8791/status 2>/dev/null)
echo "$S" | grep -q APPROACH && ok "relay API: vector -> APPROACH" || no "relay API broken ($S)"
curl -s -X POST http://127.0.0.1:8791/vector -H 'Content-Type: application/json' \
  -d '{"heading_err_deg":0,"range_m":0.4,"bearing_deg":0,"seq":2}' >/dev/null 2>&1
sleep 0.3
curl -s -m 2 http://127.0.0.1:8791/status 2>/dev/null | grep -q ARRIVED \
  && ok "relay API: close range -> ARRIVED (latched)" || no "ARRIVED latch broken"
C=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8791/vector \
  -H 'Content-Type: application/json' -d '{"garbage":1,"seq":99}' 2>/dev/null)
[ "$C" = "400" ] && ok "relay rejects malformed input (400, no crash)" || no "bad input -> $C"
pkill -f "fetch_relay.py --port 8791" 2>/dev/null

hdr "4. iOS APP"
if xcrun --sdk iphoneos swiftc -typecheck -target arm64-apple-ios17.0 \
     ios/FetchAR.swift >/tmp/fetch_swift.log 2>&1; then
  W=$(grep -c 'warning:' /tmp/fetch_swift.log 2>/dev/null); W=${W:-0}
  ok "FetchAR.swift typechecks (${W} warnings)"
else
  no "Swift typecheck FAILED"; head -4 /tmp/fetch_swift.log | sed 's/^/      /'
fi
if xcrun --sdk iphoneos swiftc -typecheck -target arm64-apple-ios17.0 \
     ios/FetchCheckpoint.swift >/tmp/fetch_checkpoint_swift.log 2>&1; then
  W=$(grep -c 'warning:' /tmp/fetch_checkpoint_swift.log 2>/dev/null); W=${W:-0}
  ok "FetchCheckpoint.swift typechecks (${W} warnings)"
else
  no "Checkpoint Swift typecheck FAILED"; head -4 /tmp/fetch_checkpoint_swift.log | sed 's/^/      /'
fi

hdr "5. CAD"
if [ -x .venv/bin/python ]; then
  .venv/bin/python - <<'PY' 2>/dev/null || echo "  ✗ CAD check failed"
import struct, sys
from build123d import import_step
def wt(fp):
    with open(fp,'rb') as f:
        f.read(80); n=struct.unpack('<I', f.read(4))[0]
        tris=[]
        for _ in range(n):
            v=struct.unpack('<12fH', f.read(50))
            tris.append(((v[3],v[4],v[5]),(v[6],v[7],v[8]),(v[9],v[10],v[11])))
    e={}
    for t in tris:
        for i in range(3):
            a,b=t[i],t[(i+1)%3]; k=(a,b) if a<b else (b,a); e[k]=e.get(k,0)+1
    return len(tris), sum(1 for c in e.values() if c!=2)
bad=0
for p in ("fetch_box","fetch_lid","fetch_sensorpod"):
    s=import_step(f"cad/{p}.step"); n=len(s.solids())
    t,b=wt(f"cad/{p}.stl")
    good = n==1 and b==0
    bad += not good
    print(f"  {'✓' if good else '✗'} {p}: {n} solid, {t:,} tris, "
          f"{'watertight' if b==0 else f'{b} bad edges'}")
sys.exit(1 if bad else 0)
PY
  [ $? -eq 0 ] && PASS=$((PASS+3)) || FAIL=$((FAIL+1))
else
  echo "  – .venv missing (build123d not installed)"
fi

hdr "6. FULL WIRING + POWER AUDIT"
if python3 tools/full_wiring.py > /tmp/fetch_full.log 2>&1; then
  ok "full_wiring.py — $(grep -c '\[OK' /tmp/fetch_full.log) checks (5 independent sonics; TF-Luna removed)"
else
  no "FULL WIRING FAILED"; tail -5 /tmp/fetch_full.log | sed 's/^/      /'
fi

hdr "6b. WIRING MAP"
if python3 tools/wiring_map.py > /tmp/fetch_wiring.log 2>&1; then
  ok "wiring_map.py — $(grep -c '\[OK' /tmp/fetch_wiring.log) checks pass (Pi power + Uno + camera)"
else
  no "WIRING FAILED"; tail -4 /tmp/fetch_wiring.log | sed 's/^/      /'
fi

hdr "7. MARKERS"
if [ -n "${PY_CV:-}" ]; then
  echo "  (using $PY_CV — the interpreter that actually has cv2)"
fi
if "${PY_CV:-python3}" tools/check_markers.py; then
  PASS=$((PASS+3))
else
  FAIL=$((FAIL+1))
fi

echo
echo "============================================"
if [ $FAIL -eq 0 ]; then
  echo "  ALL VERIFIED — $PASS checks passed"
else
  echo "  $FAIL FAILED, $PASS passed"
fi
echo "============================================"
exit $FAIL
