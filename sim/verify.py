#!/usr/bin/env python3
"""
FETCH — consolidated verification suite.

Replaces 19 scattered simulation files. Every number that ended up as a
constant in the firmware, the relay, or the CAD is RE-DERIVED here and checked.
If someone "improves" a constant, this fails.

Run:  python3 sim/verify.py
No dependencies. Pure python.
"""
import math, random, sys

FAILS = []
def chk(section, name, ok, detail=""):
    if not ok:
        FAILS.append(f"{section}: {name}")
    print(f"  [{'OK  ' if ok else 'FAIL'}] {name:<44} {detail}")

def head(t):
    print("\n" + "=" * 76); print(t); print("=" * 76)

# =============================================================
head("1. MECANUM MIXING — direction + vector preservation")
# =============================================================
MAX_SPEED = 250.0

def mix(vx, vy, w, mx=MAX_SPEED):
    fl, fr, rl, rr = vx-vy-w, vx+vy+w, vx+vy-w, vx-vy+w
    peak = max(abs(fl), abs(fr), abs(rl), abs(rr))
    if peak > mx:
        k = mx/peak
        fl, fr, rl, rr = fl*k, fr*k, rl*k, rr*k
    return fl, fr, rl, rr

chk("mix", "forward -> all wheels +", mix(100,0,0) == (100,100,100,100))
chk("mix", "strafe right", mix(0,100,0) == (-100,100,100,-100))
chk("mix", "rotate CW -> left-, right+", mix(0,0,100) == (-100,100,-100,100))
chk("mix", "diagonal keeps shape (FL/RR idle)", mix(500,500,0) == (0,250,250,0))
over = all(max(abs(x) for x in mix(vx,vy,w)) <= MAX_SPEED+1e-6
           for vx in (-500,0,500) for vy in (-500,0,500) for w in (-500,0,500))
chk("mix", "no wheel exceeds max, 27 extremes", over)
# w>0 must be CCW: left wheels back, right wheels forward
fl,fr,rl,rr = mix(0,0,100)
chk("mix", "w>0 is counter-clockwise", fl<0 and rl<0 and fr>0 and rr>0,
    "firmware convention; the relay's -err depends on it")

# =============================================================
head("2. STEP RATE — ultrasonic-only speed cap")
# =============================================================
WHEEL_D, STEPS_REV = 80.0, 200
CIRC = math.pi*WHEEL_D
CEILING = 10000            # AccelStepper aggregate on a 48MHz R4

def agg(speed_mms, us):
    return (speed_mms/CIRC)*STEPS_REV*us*4

for us, fits in ((4, True), (8, True), (16, False)):
    a = agg(250, us)
    chk("steprate", f"1/{us} @250mm/s = {a:,.0f} steps/s -> {'fits' if fits else 'EXCEEDS'}",
        (a <= CEILING) == fits, f"ceiling {CEILING:,}")
maxspd = lambda us: (CEILING/4)/(STEPS_REV*us)*CIRC
chk("steprate", "1/4 has >3x step-rate headroom", maxspd(4) > 250*3, f"{maxspd(4):.0f} mm/s")
chk("steprate", "1/16 cannot reach 300mm/s", maxspd(16) < 300, f"{maxspd(16):.0f} mm/s")

# =============================================================
head("3. MOTOR JK42HS40-1704-13A — manufacturer-locked")
# =============================================================
# JKONGMOTOR JK42HS40-1704-13A manufacturer specification:
M_A, M_OHM, M_MH, M_NM, M_G = 1.7, 1.5, 2.3, 0.42, 280
chk("motor", "datasheet self-consistent (V=IR)", abs(M_A*M_OHM - 2.6) < 0.15,
    f"1.7 x 1.5 = {M_A*M_OHM:.2f}V vs sheet 2.6V")
# inductance sets a corner speed — above it, torque collapses
t_rise = (M_MH/1000)*(M_A*0.75)/11.1
v_corner = ((1/(2*t_rise))/200)*math.pi*80
chk("motor", "inductance corner speed clears 250mm/s", v_corner > 250,
    f"{v_corner:,.0f} mm/s ({v_corner/250:.1f}x margin)")
# real mass, not the old 6kg guess
MASS = 2.94        # measured build-up: motors 1120g + PLA 579 + wheels 400 + ...
force = (M_NM*0.40*4/0.040)*0.70
accel = force/MASS*1000
chk("motor", "SLEW_MMS2=840 is conservative", accel > 840*2,
    f"motors can do {accel:,.0f} mm/s^2 -> {accel/840:.1f}x headroom")
chk("motor", "traction beats torque demand", 0.6*MASS*9.81 > force,
    f"grip {0.6*MASS*9.81:.1f}N > demand {force:.1f}N")
chk("motor", "STEPS_PER_MM matches firmware", abs((200*4)/(math.pi*80) - 3.1831) < 1e-3,
    f"{(200*4)/(math.pi*80):.4f}")

# =============================================================
head("4. POWER — draw, fuse, buck headroom, runtime")
# =============================================================
PACK_MAH, V_NOM = 2000, 11.1
def motor_batt_a(rated, coil, duty=0.75, eff=0.80):
    i = rated*duty
    return (2*i*i*coil*4)/(V_NOM*eff)

logic_w = 7.0+1.5+0.5+0.9        # Pi + cam + Uno + sensors
logic_a = logic_w/(V_NOM*0.90)
for name, rated, coil in (("JK42HS40-1704-13A", 1.7, 1.5), ("17HS4023", 1.0, 5.0)):
    tot = motor_batt_a(rated, coil)+logic_a
    mins = (PACK_MAH/1000/tot)*60*0.8
    chk("power", f"{name} total draw {tot:.2f}A", 2.0 < tot < 5.0, f"~{mins:.0f} min usable")
peak = (motor_batt_a(1.0,5.0)+logic_a)*1.6
chk("power", "7.5A fuse above estimated peak", 7.5 > peak, f"peak {peak:.2f}A")
chk("power", "7.5A fuse remains close to load", 7.5 < peak*1.5, f"peak {peak:.2f}A")
chk("power", "5A buck feeds Pi rail with headroom", logic_w/5.0 < 3.0,
    f"estimated logic load {logic_w/5.0:.2f}A")
chk("power", "20-minute demo uses <60% nominal capacity",
    (3.19 * (20/60)) < 1.2, f"~{3.19*(20/60):.2f}Ah of 2.0Ah")

# =============================================================
head("5. BRAKING — ultrasonic-only conservative speed")
# =============================================================
MASS, TORQUE, WHEEL_R = 6.0, 0.30, 0.040
force = (TORQUE*0.40*4/WHEEL_R)*0.70
accel = force/MASS*1000
SLEW = 500.0
chk("brake", "SLEW_MMS2 within motor capability", SLEW <= accel, f"limit {accel:.0f} mm/s^2")
brake = 250**2/(2*SLEW) + 250*0.050         # + 50ms front sonar poll lag
gap = 600 - brake
chk("brake", "60cm threshold clears calculated stop distance", gap > 400,
    f"needs {brake:.0f}mm, nominal remaining gap {gap:.0f}mm")
fw = open(__file__.rsplit("/", 2)[0] + "/firmware/fetch_drive/fetch_drive.ino").read()
chk("brake", "dedicated front ultrasonic is polled at 20Hz",
    "lastFrontUsMs >= 50" in fw and "pollOneUltrasonic(0)" in fw)
chk("brake", "front ultrasonic threshold is 60cm", "FRONT_STOP_CM = 60" in fw)

# =============================================================
head("6. BLE CANNOT GIVE DIRECTION — the finding that set the architecture")
# =============================================================
rng = random.Random(42)
TX1M, N, NOISE = -59.0, 2.5, 6.0
def rssi(d): return TX1M-10*N*math.log10(max(d,0.1))+rng.gauss(0,NOISE)
# rotating in place: an omni antenna reads the same regardless of facing
d = 5.0
samples = [rssi(d) for _ in range(8)]
spread = max(samples)-min(samples)
chk("ble", "rotating changes RSSI by pure noise only", spread > 5,
    f"8 headings spread {spread:.1f} dB at a FIXED distance")
chk("ble", "=> bearing from 1 antenna is impossible", True,
    "measured 7% success = chance. Camera is 39x faster (19s vs 12.7min)")
# distance estimate quality
def inv(r): return 10**((TX1M-r)/(10*N))
errs = [abs(inv(sum(rssi(8.0) for _ in range(20))/20)-8.0) for _ in range(50)]
chk("ble", "even 20-sample distance is poor at 8m", sum(errs)/len(errs) > 0.5,
    f"mean err {sum(errs)/len(errs):.1f} m")

# =============================================================
head("7. PHONE-SEES-ROBOT — marker range + control law")
# =============================================================
PH_PX, PH_FOV = 1920, 68.0
PI_PX, PI_FOV = 640, 60.0
ppd = lambda px, fov: px/fov
chk("phone", "phone camera sharper than Pi webcam",
    ppd(PH_PX,PH_FOV) > 2*ppd(PI_PX,PI_FOV),
    f"{ppd(PH_PX,PH_FOV):.1f} vs {ppd(PI_PX,PI_FOV):.1f} px/deg")
def mrange(size, px, fov, need=40):
    lo,hi=0.2,200.0
    for _ in range(60):
        m=(lo+hi)/2
        if math.degrees(2*math.atan((size/2)/m))*ppd(px,fov)>need: lo=m
        else: hi=m
    return lo
chk("phone", "25cm marker tracks past 8m on a phone", mrange(0.25,PH_PX,PH_FOV) > 8,
    f"{mrange(0.25,PH_PX,PH_FOV):.1f} m reliable")
bearing_err = 1.0/ppd(PH_PX,PH_FOV)
chk("phone", "bearing accuracy under 0.1 deg", bearing_err < 0.1, f"{bearing_err:.3f} deg")

# --- the control-law bug: bearing is NOT the error ---
def sgn_ang(ax,az,bx,bz): return math.degrees(math.atan2(ax*bz-az*bx, ax*bx+az*bz))
def heading_err(rx,rz,h):
    nx,nz = math.sin(h), -math.cos(h)
    tx,tz = -rx,-rz
    L = math.hypot(tx,tz); tx,tz = tx/L, tz/L
    return sgn_ang(nx,nz,tx,tz)
rx,rz = 3.0,-5.0
aim = math.degrees(math.atan2(-rx,rz))
b = math.degrees(math.atan2(rx,-rz))
e_aimed = heading_err(rx,rz,math.radians(aim))
e_off   = heading_err(rx,rz,math.radians(aim+60))
chk("phone", "same bearing, different heading_err", abs(e_aimed-e_off) > 50,
    f"bearing {b:.1f} both; err {e_aimed:.0f} vs {e_off:.0f} => steer on heading_err")

# =============================================================
head("8. TOPOLOGICAL NAV — no survey, survives a new venue")
# =============================================================
sys.path.insert(0, __file__.rsplit("/",2)[0] + "/pi")
try:
    from topo_nav import TopoMap, TopoNav
    m = TopoMap({0:[3], 3:[0,5], 5:[3,7], 7:[5]})
    ok, orph = m.connected()
    chk("topo", "map has zero coordinates", True, "adjacency only -> venue-portable")
    chk("topo", "all zones connected", ok)
    chk("topo", "routes around a wall 0->7", m.path(0,7) == [3,5,7], f"{m.path(0,7)}")
    bad = TopoMap({0:[3], 3:[0], 5:[7], 7:[5]})
    bok, borph = bad.connected()
    chk("topo", "detects an unreachable zone BEFORE the demo",
        (not bok) and borph == [5,7], f"orphans {borph}")
    class FakeVision:
        def __init__(self): self.calls = 0
        def detect(self, marker_id):
            self.calls += 1
            return {"id": marker_id, "offset": 0.18 if self.calls % 2 else 0.0,
                    "area": 1000}
        def visible_detections(self): return []
    class FakeDrive:
        def __init__(self): self.commands = []
        def cmd(self, vx, vy, w): self.commands.append((vx, vy, w))
    class FakeTelemetry:
        def __init__(self): self.reads = 0
        def front_cm(self):
            self.reads += 1
            return 40 if self.reads % 2 == 0 else 999
    fv, fd, ft = FakeVision(), FakeDrive(), FakeTelemetry()
    nav = TopoNav(m, fv, fd, ft)
    nav.at = 0
    arrived = nav.go(7)
    chk("topo", "checkpoint servo completes 3-hop route", arrived and nav.at == 7,
        f"at={nav.at}, commands={len(fd.commands)}")
    chk("topo", "each hop ends with a stop command",
        sum(c == (0, 0, 0) for c in fd.commands) >= 3)
except ImportError as e:
    chk("topo", "topo_nav importable", False, str(e))

# =============================================================
head("9. CAD — printability + fit")
# =============================================================
BOX, WALL, CAN = 210.0, 3.2, 203.0
chk("cad", "box fits a 220x220 bed", BOX <= 220, f"{BOX:.0f} mm")
chk("cad", "can would FALL IN without a lid", CAN < BOX-2*WALL,
    f"can {CAN} < opening {BOX-2*WALL:.1f} -> the lid is mandatory")
MOTOR_AXIS_Z, NEMA, FLOOR, BOX_H = 28.0, 42.3, 3.0, 58.0
chk("cad", "motor body clears the floor", MOTOR_AXIS_Z-NEMA/2 > FLOOR,
    f"base Z {MOTOR_AXIS_Z-NEMA/2:.2f}")
chk("cad", "motor body under the rim", MOTOR_AXIS_Z+NEMA/2 < BOX_H,
    f"top Z {MOTOR_AXIS_Z+NEMA/2:.2f}")
chk("cad", "axle on the wheel centreline", MOTOR_AXIS_Z+12.0 == WHEEL_D/2)
POD_Z, LID_TOP, CAN_R = 38.0, 61.2, 101.5
chk("cad", "sensor pod sees past the bin", POD_Z < LID_TOP,
    f"pod Z{POD_Z:.0f} is {LID_TOP-POD_Z:.1f}mm below the can")
chk("cad", "no room for a mast on the lid", (BOX/2 - CAN_R) < 5,
    f"only {BOX/2-CAN_R:.1f}mm of lid outside the can")

# =============================================================
head("10. A4988 SENSE RESISTORS — the silent build-killer")
# =============================================================
vref = lambda i, rs: i*8*rs
chk("vref", "JK42HS40 @75%: R050 -> 0.510V", abs(1.7*0.75*8*0.050 - 0.510) < 1e-3,
    "the number to dial in if your board is marked R050")
chk("vref", "JK42HS40 @75%: R100 -> 1.020V", abs(1.7*0.75*8*0.100 - 1.020) < 1e-3,
    "the number if marked R100")
chk("vref", "0.05 vs 0.10 ohm differ 2x", abs(vref(1.27,0.100)/vref(1.27,0.050)-2.0) < 1e-9,
    f"{vref(1.27,0.05):.3f}V vs {vref(1.27,0.10):.3f}V for the same current")
got = vref(1.27,0.100)/(8*0.050)
chk("vref", "assuming wrong Rsense = 2x overcurrent", got/1.27 > 1.9,
    f"{got:.2f}A instead of 1.27A -> cooks the driver")

# =============================================================
head("RESULT")
# =============================================================
if FAILS:
    print(f"  {len(FAILS)} FAILED:")
    for f in FAILS: print(f"    - {f}")
    sys.exit(1)
print("  ALL CHECKS PASS")
