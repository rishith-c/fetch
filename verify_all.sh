#!/usr/bin/env bash
# Verify only the actual TT-motor / two-L298N FETCH baseline.
# Physical commissioning in docs/FINAL_BUILD_MANUAL.md remains mandatory.
set -uo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:$PATH"

PASS=0
FAIL=0
ok(){ printf '  PASS %s\n' "$1"; PASS=$((PASS+1)); }
no(){ printf '  FAIL %s\n' "$1"; FAIL=$((FAIL+1)); }
section(){ printf '\n=== %s ===\n' "$1"; }

pick_python(){
  local module="$1"
  local candidate
  for candidate in /usr/bin/python3 /opt/homebrew/bin/python3 python3; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    "$candidate" -c "import $module" >/dev/null 2>&1 && {
      printf '%s\n' "$candidate"
      return 0
    }
  done
  return 1
}

section "ACTUAL-BUILD ENGINEERING MODEL"
if python3 sim/verify_tt_fetch.py >/tmp/fetch_tt_sim.log 2>&1; then
  ok "$(tail -n 1 /tmp/fetch_tt_sim.log)"
else
  no "engineering model"
  tail -n 15 /tmp/fetch_tt_sim.log | sed 's/^/       /'
fi

section "BEHAVIOR AND CONSISTENCY TESTS"
if python3 -m unittest -v tests/test_actual_fetch.py >/tmp/fetch_tt_tests.log 2>&1; then
  ok "$(grep -E '^Ran [0-9]+' /tmp/fetch_tt_tests.log | tail -n 1)"
else
  no "actual-build tests"
  tail -n 25 /tmp/fetch_tt_tests.log | sed 's/^/       /'
fi

section "UNO R4 FIRMWARE"
if ! command -v arduino-cli >/dev/null 2>&1; then
  no "arduino-cli is not installed"
else
  if ARDUINO_OUT=$(arduino-cli compile --fqbn arduino:renesas_uno:minima firmware/tt_fetch_drive 2>&1); then
    ok "tt_fetch_drive compiles for Uno R4 Minima"
    printf '%s\n' "$ARDUINO_OUT" | tail -n 2 | sed 's/^/       /'
  else
    no "tt_fetch_drive compile"
    printf '%s\n' "$ARDUINO_OUT" | tail -n 15 | sed 's/^/       /'
  fi
fi

section "RASPBERRY PI PYTHON"
if python3 -m py_compile pi/topo_nav.py pi/topo_server.py tools/make_topo_map.py \
   tools/validate_commissioning.py; then
  ok "Pi server, navigation, and map tool compile"
else
  no "Pi Python compile"
fi

if bash -n pi/install_fetch_service.sh \
   && bash pi/install_fetch_service.sh --dry-run \
      --serial /dev/serial/by-id/TEST_UNO \
      --map config/topo_map.demo.json --start-zone 0 \
      | grep -q 'DRY RUN PASS'; then
  ok "Pi systemd installer validates map/config without changing the system"
else
  no "Pi systemd installer dry run"
fi

if python3 tools/validate_commissioning.py \
   commissioning/acceptance_template.json >/tmp/fetch_blank_acceptance.log 2>&1; then
  no "blank physical-acceptance template incorrectly passed"
else
  ok "blank physical-acceptance template is correctly rejected"
fi

MAP_TMP=$(mktemp /tmp/fetch_map.XXXXXX.json)
if python3 tools/make_topo_map.py --edges 0-1,1-2,2-3 --output "$MAP_TMP" >/dev/null \
   && python3 pi/topo_nav.py --map "$MAP_TMP" --check | grep -q '^CONNECTED:'; then
  ok "bidirectional commissioned graph validates"
else
  no "topological-map validation"
fi
rm -f "$MAP_TMP"

section "iOS SOURCE"
if xcrun --sdk iphoneos swiftc -parse-as-library -typecheck -target arm64-apple-ios17.0 \
   ios/FetchCheckpoint.swift >/tmp/fetch_swift.log 2>&1; then
  ok "FetchCheckpoint.swift typechecks for iOS 17"
else
  no "iOS Swift typecheck"
  head -n 15 /tmp/fetch_swift.log | sed 's/^/       /'
fi
if [ -f ios/FetchCheckpoint.xcodeproj/project.pbxproj ] \
   && xcodebuild -project ios/FetchCheckpoint.xcodeproj \
      -scheme FetchCheckpoint -sdk iphonesimulator -configuration Debug \
      CODE_SIGNING_ALLOWED=NO build >/tmp/fetch_xcodebuild.log 2>&1; then
  ok "FetchCheckpoint Xcode project builds for iOS Simulator"
else
  no "iOS Xcode project build"
  tail -n 20 /tmp/fetch_xcodebuild.log 2>/dev/null | sed 's/^/       /'
fi

section "CHECKPOINT POSTERS"
PY_CV=$(pick_python cv2 || true)
if [ -z "$PY_CV" ]; then
  no "no Python interpreter with OpenCV ArUco"
elif "$PY_CV" markers/make_checkpoints.py >/tmp/fetch_markers.log 2>&1 \
     && grep -q '12/12 AprilTags detected' /tmp/fetch_markers.log \
     && grep -q '12/12 QR codes decoded' /tmp/fetch_markers.log; then
  ok "12 AprilTags and 12 QR codes regenerate and decode"
else
  no "checkpoint poster generation/decode"
  tail -n 20 /tmp/fetch_markers.log | sed 's/^/       /'
fi

section "AUTHORITATIVE BASELINE"
if grep -q 'two L298N' README.md \
   && grep -q 'two L298N' docs/FINAL_BUILD_MANUAL.md \
   && grep -q 'No TF-Luna' README.md \
   && grep -q 'Go/no-go record' docs/FINAL_BUILD_MANUAL.md; then
  ok "README and final manual identify the same final hardware and physical gates"
else
  no "authoritative documentation baseline"
fi

printf '\n============================================\n'
printf 'Software verification: %d passed, %d failed\n' "$PASS" "$FAIL"
if [ "$FAIL" -eq 0 ]; then
  printf 'SOFTWARE VERIFIED — physical commissioning is still required.\n'
else
  printf 'NOT VERIFIED — repair every failure before hardware commissioning.\n'
fi
printf '============================================\n'
exit "$FAIL"
