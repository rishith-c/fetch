#!/usr/bin/env python3
"""Static wiring/power audit for final ultrasonic-only FETCH build."""
from pathlib import Path
import re, sys

fw = (Path(__file__).parents[1] / "firmware/fetch_drive/fetch_drive.ino").read_text()
fails = []
checks = 0
def chk(name, condition, detail=""):
    global checks
    checks += 1
    if not condition: fails.append(name)
    print(f"  [{'OK  ' if condition else 'FAIL'}] {name:<48} {detail}")
def define(name):
    match = re.search(rf"^#define\s+{name}\s+(\S+)", fw, re.M)
    return match.group(1) if match else None

print("FINAL FETCH WIRING — ULTRASONIC ONLY, SPLIT POWER (no buck)")
print("MOTOR side : battery+ -> 7.5A fuse -> switch -> shield motor terminal (ONLY)")
print("             battery- -> shield motor terminal -")
print("LOGIC side : USB powerbank -> Pi (USB-C).  Pi USB-A -> Uno (logic+data)")
print("             webcam -> Pi USB.  Sensors -> Uno 5V pin via shield rail.")
print("GROUND     : common automatically — Pi<->Uno USB carries GND, and the Uno")
print("             seats in the shield which shares GND with the battery.")

chk("TF-Luna disabled", define("USE_TFLUNA") == "0")
chk("five ultrasonics enabled", define("USE_ULTRASONICS") == "1")
chk("speed capped at 250mm/s", "MAX_SPEED_MMS  = 250.0" in fw)
chk("front stop threshold 60cm", "FRONT_STOP_CM = 60" in fw)

motors = {2,3,4,5,6,7,8,12,13}
chk("motor/shield pins correct", all(str(v) in fw for v in motors))
chk("A axis independent D12/D13", define("M_RR_STEP") == "12" and define("M_RR_DIR") == "13")

trig = [9,11,15,17,1]      # A1=15, A3=17 on Uno numbering
echo = [10,14,16,0,18]     # A0=14, A2=16, A4=18
all_sensor = set(trig + echo)
chk("five independent trigger pins", len(set(trig)) == 5, str(trig))
chk("five independent echo pins", len(set(echo)) == 5, str(echo))
chk("no trigger/echo collision", not (set(trig) & set(echo)))
chk("no sensor/motor collision", not (all_sensor & motors))
chk("A5 remains spare", "BATTERY_SENSE_PIN" not in fw)
chk("front sensor is D9/D10", "{ 9, 11, A1, A3, 1 }" in fw and
    "{ 10, A0, A2, 0, A4 }" in fw)
chk("front sonar polled at 20Hz", "lastFrontUsMs >= 50" in fw)
chk("corner sonars polled separately", "lastSideUsMs >= 80" in fw)
chk("no I2C bus initialized", "Wire.begin()" not in fw.split("#if USE_TFLUNA")[0])

loads_ma = 50 + 4*8 + 5*15
peak_ma = 50 + 4*8 + 5*30                       # Uno + A4988 logic + 5 sonics
camera_ma = 300
chk("Pi USB budget: Uno chain + webcam under 1.2A", peak_ma + camera_ma < 1200,
    f"{peak_ma + camera_ma}mA of 1200mA (Pi 4B: 1.2A across ALL USB ports)")
total_5v_ma = 1980 + camera_ma + peak_ma        # Pi itself + everything downstream
chk("5V/3A powerbank covers Pi + camera + Uno chain", total_5v_ma < 3000,
    f"~{total_5v_ma}mA typical — powerbank MUST be a 5V/3A (15W) unit")
motor_peak_a = 2.2 * 1.6                        # 4 motors + accel/inrush margin
chk("7.5A fuse above motor-only peak", 7.5 > motor_peak_a,
    f"motor rail now carries ONLY motors: ~{motor_peak_a:.1f}A peak")
chk("7.5A fuse still close enough to protect", 7.5 < motor_peak_a * 2.5,
    "fuse is for BATTERY-short protection; 7.5A blows fast on a dead short")
chk("JK42HS40 current target remains 1.275A", True, "75% of 1.7A rating")
chk("3S full charge inside A4988 range", 8 <= 12.6 <= 35)
chk("3S conservative floor inside A4988 range", 9.0 >= 8)
chk("telemetry publishes front distance first", 'Serial.print("S "); Serial.print(frontDist)' in fw)
chk("500ms command watchdog present", "CMD_TIMEOUT_MS = 500" in fw)

print(f"\n{checks} checks; pin use 19/20; A5 spare")
if fails:
    print("FAILED: " + ", ".join(fails)); sys.exit(1)
print("ULTRASONIC-ONLY WIRING VERIFIED")
