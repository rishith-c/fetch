#!/usr/bin/env python3
"""Human-readable final topology plus consistency checks."""
from pathlib import Path
import sys

root = Path(__file__).parents[1]
fw = (root / "firmware/fetch_drive/fetch_drive.ino").read_text()
server = (root / "pi/topo_server.py").read_text()
fails = []
def chk(name, ok, detail=""):
    if not ok: fails.append(name)
    print(f"  [{'OK  ' if ok else 'FAIL'}] {name:<43} {detail}")

print("""
 iPhone --Wi-Fi--> Pi 4B --USB--> Uno R4 + CNC Shield --> 4 motors
                         |                     |
                         |                     +--> 5 x HC-SR04
                         +--> USB webcam

 battery+ --7.5A fuse--switch--+--> shield VMOT
                              +--> 5V/5A buck --> Pi
 battery- --------------------+--> common negative
""")
chk("Pi opens USB webcam", "VideoCapture" in server)
chk("Pi opens Uno serial", "serial.Serial" in server)
chk("TF-Luna disabled", "#define USE_TFLUNA 0" in fw)
chk("five independent sonar triggers", "{ 9, 11, A1, A3, 1 }" in fw)
chk("five independent sonar echoes", "{ 10, A0, A2, 0, A4 }" in fw)
chk("front range sent to Pi", "Serial.print(frontDist)" in fw)
chk("A axis D12/D13", "#define M_RR_STEP 12" in fw and "#define M_RR_DIR  13" in fw)
chk("watchdog stops stale Pi", "CMD_TIMEOUT_MS = 500" in fw)

if fails:
    print("FAILED: " + ", ".join(fails)); sys.exit(1)
print("FINAL TOPOLOGY VERIFIED")
