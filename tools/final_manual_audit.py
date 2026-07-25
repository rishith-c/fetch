#!/usr/bin/env python3
"""Verify the authoritative manual agrees with firmware and final hardware."""
from pathlib import Path
import sys

root = Path(__file__).parents[1]
manual = (root / "docs" / "FINAL_BUILD_MANUAL.md").read_text()
fw = (root / "firmware/fetch_drive/fetch_drive.ino").read_text()
checks = [
    ("exact motor", "JK42HS40-1704-13A" in manual),
    ("TF-Luna excluded", "no TF-Luna" in manual and "#define USE_TFLUNA 0" in fw),
    ("five sonars", "Five HC-SR04" in manual and "#define US_N 5" in fw),
    ("sensor pin arrays", "{ 9, 11, A1, A3, 1 }" in fw and "{ 10, A0, A2, 0, A4 }" in fw),
    ("US1 D9/D10", "TRIG→D9" in manual and "ECHO→D10" in manual),
    ("US5 D1/A4", "TRIG→D1" in manual and "ECHO→A4" in manual),
    ("A5 spare", "Leave A5 unconnected" in manual),
    ("A axis D12/D13", "independent D12/D13" in manual),
    ("quarter microstep", "MS1 and MS2" in manual and "Leave MS3 open" in manual),
    ("250 speed", "MAX_SPEED_MMS  = 250.0" in fw and "250mm/s" in manual),
    ("500 slew", "SLEW_MMS2      = 500.0" in fw and "500mm/s²" in manual),
    ("60cm front stop", "FRONT_STOP_CM = 60" in fw and "Front stop | 60cm" in manual),
    ("500ms watchdog", "CMD_TIMEOUT_MS = 500" in fw and "Command watchdog | 500ms" in manual),
    ("7.5A fuse", "7.5A fuse" in manual),
    ("5.1V buck", "5.1V/5A" in manual),
    ("one battery at a time", "one 11.1v 2000mah sm2p battery installed" in manual.lower()),
    ("no battery monitor", "Leave A5 unconnected" in manual and "BATTERY_SENSE" not in fw),
    ("camera required", "UVC USB webcam" in manual and "VideoCapture" in (root / "pi/topo_server.py").read_text()),
    ("start zone explicit", "--start-zone 0" in manual),
    ("numbered through final", "106. Perform two complete successful summons" in manual),
]
fails = []
for name, ok in checks:
    print(f"  [{'OK  ' if ok else 'FAIL'}] {name}")
    if not ok: fails.append(name)
if fails:
    print("FAILED: " + ", ".join(fails)); sys.exit(1)
print(f"FINAL MANUAL VERIFIED — {len(checks)} checks")
