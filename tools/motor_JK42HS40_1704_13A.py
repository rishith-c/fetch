#!/usr/bin/env python3
"""
FETCH — JK42HS40-1704-13A motor specification.

Source: JKONGMOTOR manufacturer specification for JK42HS40-1704-13A.
https://www.jkongmotor.com/nema-17-jk42hs40-1704-13a-hybrid-stepper-motor.html

WHY THIS FILE EXISTS
    Three of the earlier design assumptions were WRONG, and knowing the exact
    motor fixes all three — in your favour:

      torque   assumed 0.30 Nm  ->  actual 0.42 Nm
      mass     assumed 6.0 kg   ->  actual ~2.9 kg   (motors are 280g x4)
      accel    assumed 1400 mm/s^2 -> actual ~4100   (3x headroom)

    So the firmware's SLEW_MMS2 = 500 is not marginal, it is deeply
    conservative. Good — but now we know it, instead of hoping.

Run:  python3 tools/motor_JK42HS40_1704_13A.py
"""
import math

# ---------------- datasheet, quoted ----------------
MODEL          = "JK42HS40-1704-13A"
STEP_ANGLE_DEG = 1.8            # -> 200 steps/rev
PHASE_V        = 2.6            # Vdc
PHASE_A        = 1.7            # A  <-- the number for Vref
PHASE_OHM      = 1.5            # ohm +/-10%
PHASE_MH       = 2.3            # mH +/-20% @1kHz
HOLD_TORQUE_NM = 0.42           # 42 N.cm
ROTOR_INERTIA  = 54e-7          # 54 g.cm^2 -> kg.m^2
MASS_KG        = 0.280          # 280 g each
LENGTH_MM      = 40.0
SHAFT_DIA_MM   = 5.0
WIRES          = 4

# ---------------- our build ----------------
N_MOTORS   = 4
SUPPLY_V   = 11.1               # 3S LiPo nominal
VREF_DUTY  = 0.75               # run at 75% of rated
WHEEL_D_MM = 80.0
MICROSTEP  = 4

TARGET_A = PHASE_A * VREF_DUTY


def banner(t):
    print("\n" + "=" * 72); print(t); print("=" * 72)


banner(f"{MODEL} — DATASHEET (verbatim)")
for k, v in (("step angle", f"{STEP_ANGLE_DEG}deg -> {int(360/STEP_ANGLE_DEG)} steps/rev"),
             ("phase current", f"{PHASE_A} A"),
             ("phase resistance", f"{PHASE_OHM} ohm +/-10%"),
             ("phase inductance", f"{PHASE_MH} mH +/-20%"),
             ("phase voltage", f"{PHASE_V} Vdc"),
             ("holding torque", f"{HOLD_TORQUE_NM} Nm (42 N.cm)"),
             ("mass", f"{MASS_KG*1000:.0f} g each -> {MASS_KG*N_MOTORS*1000:.0f} g for 4"),
             ("body length", f"{LENGTH_MM} mm"),
             ("shaft", f"{SHAFT_DIA_MM} mm")):
    print(f"  {k:<20} {v}")

# ---------------- 1. VREF — the number you actually dial in ----------------
banner("1. VREF — set this on ALL FOUR drivers")
print(f"  rated {PHASE_A} A  x  {VREF_DUTY:.0%} duty  =  {TARGET_A:.3f} A target")
print()
print(f"  {'your board':<44} {'Rsense':>7} {'SET VREF':>10}")
print("  " + "-" * 64)
for rs, name in ((0.050, "Pololu genuine / StepStick  (marked R050)"),
                 (0.100, "common clone 5-packs        (marked R100)"),
                 (0.200, "older clones               (marked R200)")):
    print(f"  {name:<44} {rs:>6.3f}o {TARGET_A*8*rs:>9.3f} V")
print()
print("  >>> READ THE TWO TINY RESISTORS NEXT TO THE TRIM POT FIRST. <<<")
print(f"      Guess 0.100 when you have 0.050 -> {TARGET_A*8*0.100/(8*0.050):.2f} A. That cooks the driver.")

# ---------------- 2. sanity: does the datasheet self-agree? ----------------
banner("2. DATASHEET SELF-CONSISTENCY")
v_calc = PHASE_A * PHASE_OHM
print(f"  V = I x R = {PHASE_A} x {PHASE_OHM} = {v_calc:.2f} V   vs datasheet {PHASE_V} V")
print(f"  -> {'consistent' if abs(v_calc-PHASE_V) < 0.15 else 'MISMATCH — check the sheet'}")
print(f"  (the A4988 chops {SUPPLY_V}V down to ~{v_calc:.1f}V; that is normal and why")
print(f"   battery current is LOWER than {PHASE_A}A per phase)")

# ---------------- 3. NEW: inductance sets a speed ceiling ----------------
banner("3. INDUCTANCE — the speed limit nobody checks")
L, R = PHASE_MH / 1000.0, PHASE_OHM
t_rise = L * TARGET_A / SUPPLY_V          # time to drive current into the coil
f_corner = 1.0 / (2 * t_rise)             # full-steps/s before torque collapses
circ = math.pi * WHEEL_D_MM
v_corner = (f_corner / 200) * circ
print(f"  L/R electrical time constant   {L/R*1000:.2f} ms")
print(f"  time to reach {TARGET_A:.2f}A from {SUPPLY_V}V   {t_rise*1000:.3f} ms")
print(f"  corner speed (torque starts dropping)  ~{f_corner:,.0f} full-steps/s")
print(f"  = {v_corner:,.0f} mm/s at the wheel")
print()
ok = v_corner > 250
print(f"  firmware maximum 250 mm/s -> {'OK, ' if ok else 'PROBLEM, '}"
      f"{v_corner/250:.1f}x margin before torque falls off")
print(f"  A higher supply voltage would raise this. 11.1V is fine for our speed.")

# ---------------- 4. mass + acceleration, for real ----------------
banner("4. REAL MASS + ACCELERATION")
parts = [
    ("4x JK42HS40-1704-13A", MASS_KG * N_MOTORS * 1000),
    ("chassis box (PLA)", 381),
    ("lid (PLA)", 176),
    ("sensor pod (PLA)", 22),
    ("4x mecanum wheel", 400),
    ("3S 2000mAh LiPo", 180),
    ("trashcan", 400),
    ("Pi 4B + Uno + shield + drivers", 111),
    ("wiring, fasteners, misc", 150),
]
total_g = sum(p[1] for p in parts)
for n, g in parts:
    print(f"  {n:<34} {g:>6.0f} g")
print("  " + "-" * 44)
print(f"  {'TOTAL':<34} {total_g:>6.0f} g  = {total_g/1000:.2f} kg")

mass = total_g / 1000.0
USABLE = 0.40          # dynamic torque at speed, fraction of holding
MEC_EFF = 0.70         # mecanum rollers waste force in the 45deg vectors
wheel_r = WHEEL_D_MM / 2000.0
force = (HOLD_TORQUE_NM * USABLE * N_MOTORS / wheel_r) * MEC_EFF
accel = force / mass * 1000
print()
print(f"  usable torque/motor  {HOLD_TORQUE_NM*USABLE:.3f} Nm  ({USABLE:.0%} of holding at speed)")
print(f"  tractive force       {force:.1f} N   (mecanum eff {MEC_EFF:.0%})")
print(f"  >>> max accel        {accel:,.0f} mm/s^2")
print(f"  firmware SLEW_MMS2   500 mm/s^2  -> {accel/500:.1f}x headroom  "
      f"[{'SAFE' if accel > 500 else 'TOO AGGRESSIVE'}]")

# traction check — can the floor even take it?
MU = 0.6
traction_n = MU * mass * 9.81
print()
print(f"  traction limit ({MU} mu)  {traction_n:.1f} N vs {force:.1f} N demanded")
print(f"  -> {'grip is fine' if traction_n > force else 'WHEELS WILL SLIP before torque runs out'}")

# ---------------- 5. power, with the real motor ----------------
banner("5. POWER — with the real 1.7A / 1.5 ohm")
w_motor = 2 * (TARGET_A ** 2) * PHASE_OHM
w_total = w_motor * N_MOTORS
batt_a = w_total / (SUPPLY_V * 0.80)
logic_a = (7.0 + 1.5 + 0.5 + 0.4) / (SUPPLY_V * 0.90)
print(f"  per motor (2 phases on)  {w_motor:.1f} W")
print(f"  4 motors                 {w_total:.1f} W")
print(f"  battery current, motors  {batt_a:.2f} A")
print(f"  battery current, logic   {logic_a:.2f} A")
print(f"  TOTAL                    {batt_a+logic_a:.2f} A")
runtime = (2.0 / (batt_a + logic_a)) * 60 * 0.8
print(f"  2000mAh usable runtime   ~{runtime:.0f} min of continuous driving")
print(f"  7.5A fuse vs {(batt_a+logic_a)*1.6:.1f} A peak -> "
      f"{'correct' if 7.5 > (batt_a+logic_a)*1.6 else 'WRONG'}")

# ---------------- 6. steps ----------------
banner("6. STEPS PER MM — the firmware constant")
spm = (200 * MICROSTEP) / circ
print(f"  STEPS_PER_MM = (200 x {MICROSTEP}) / (pi x {WHEEL_D_MM:.0f}) = {spm:.4f}")
print(f"  at 250 mm/s -> {250*spm:,.0f} steps/s per motor, {250*spm*4:,.0f} aggregate")
print(f"  AccelStepper ceiling ~10,000 -> {'fits' if 250*spm*4 < 10000 else 'EXCEEDS'}")
print()
print(f"  !! IF YOUR WHEELS ARE NOT {WHEEL_D_MM:.0f}mm, change WHEEL_DIA_MM in the")
print(f"     firmware. Everything above scales with it.")
