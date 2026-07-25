#!/usr/bin/env python3
"""Deterministic engineering checks for the actual TT/L298N FETCH build."""

import math

checks = []


def check(name, condition, detail=""):
    checks.append((name, bool(condition), detail))
    print(("PASS" if condition else "FAIL"), name, detail)


# Pin budget: direct L298 control needs 12; shared-trigger sonar needs 6.
motor_pins = {5, 2, 4, 6, 7, 8, 9, 12, 13, 10, 14, 15}
sonar_pins = {3, 11, 16, 17, 18, 19}
check("18 unique signal pins", len(motor_pins | sonar_pins) == 18)
check("motor/sonar pins do not overlap", motor_pins.isdisjoint(sonar_pins))
check("D0/D1 remain free for diagnostics", (motor_pins | sonar_pins).isdisjoint({0, 1}))
check("four enable pins are PWM capable", {5, 6, 9, 10} <= {3, 5, 6, 9, 10, 11})

# Camera geometry. At 1280 px and 70 degree horizontal FOV, calculate tag
# width in pixels using the pinhole relation. A 180 mm tag is deliberately used.
frame_width = 1280
hfov = math.radians(70)
focal_px = frame_width / (2 * math.tan(hfov / 2))
tag_m = 0.180


def tag_pixels(distance_m):
    return focal_px * tag_m / distance_m


check("180 mm tag >=30 px at 5 m (lab extension only)", tag_pixels(5.0) >= 30,
      f"{tag_pixels(5.0):.1f}px")
check("180 mm tag >=50 px at 3 m (commissioned route limit)", tag_pixels(3.0) >= 50,
      f"{tag_pixels(3.0):.1f}px")

# Stopping envelope: 140 mm/s command, 500 ms firmware watchdog, 0.43 s slew
# from full command, and a conservative 100 mm mechanical coast allowance.
speed = 140.0
watchdog_travel = speed * 0.5
slew_travel = 0.5 * speed * 0.43
coast = 100.0
total_stop = watchdog_travel + slew_travel + coast
check("60 cm front threshold leaves about 400 mm modeled margin", 600 - total_stop >= 395,
      f"estimated stop travel {total_stop:.0f}mm, margin {600-total_stop:.0f}mm")

# Battery envelope. Compute is on a separate power bank. Use only 80% of the
# advertised 22.2 Wh and examine the worst allowed 3 A battery-side draw.
usable_wh = 11.1 * 2.0 * 0.80
for amps in (1.5, 2.0, 2.5, 3.0):
    minutes = usable_wh / (11.1 * amps) * 60
    check(f"runtime at {amps:.1f} A exceeds 20 min", minutes >= 20,
          f"{minutes:.1f}min")

# With two 6.5 V rails, 90% conversion and a 10.5 V low-battery condition,
# a 3 A battery limit still permits ~4.36 A aggregate motor-rail current.
available_motor_a = 10.5 * 3.0 * 0.90 / 6.5
check("3 A battery envelope supplies >4.3 A at motor rails", available_motor_a > 4.3,
      f"{available_motor_a:.2f}A aggregate")

# L298 output at 1 A uses the ST typical 1.8 V total bridge drop. The result is
# inside the motor's 3-6 V range when the adjustable rails are set to 6.5 V.
motor_v_typical = 6.5 - 1.8
check("typical 1 A motor voltage is in 3-6 V range", 3.0 <= motor_v_typical <= 6.0,
      f"{motor_v_typical:.1f}V")

failed = [name for name, passed, _ in checks if not passed]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
if failed:
    raise SystemExit("failed: " + ", ".join(failed))
