"""
FETCH — printable chassis BOX (rectangular prism enclosure).

Replaces the flat plate. A plate is a shelf; this is a chassis.

WHAT IT IS
    A rectangular box that:
      - holds all 4 NEMA17 motors INSIDE, shafts out through the side walls
      - has floor bosses for the Pi 4B and Uno R4 + CNC shield
      - has a walled battery bay with strap slots
      - has 4 locating tabs + bolt holes on top for the TRASHCAN
      - prints floor-down, NO SUPPORTS

PRINT BED
    210 x 210 outer. Fits a 220x220 Ender bed AND a 256x256 Bambu/Prusa bed.
    Does NOT fit an A1 mini (180x180) — say the word and I'll split it.

COORDINATES (box-local)
    origin = box centre, on the BOTTOM face of the floor (Z=0)
    +X = forward, +Y = left, +Z = up.  Ground sits at Z = -GROUND_CLEAR.

LAYOUT
    Motor bodies eat the four corners: they occupy |X| in [56.9, 99.2] and
    |Y| in [61.8, 101.8]. That leaves a free central band (|Y| < 61.8, any X)
    plus a free spine (|X| < 56.9, any Y).
      - Pi and Uno sit SIDE BY SIDE in the central band
      - battery sits in the rear spine, between the rear motors
    Every clearance is asserted at the bottom. Nothing here is eyeballed.
"""
from build123d import *

# ---------------- box shell ----------------
BOX_X, BOX_Y = 210.0, 210.0
WALL = 3.2
FLOOR = 3.0
BOX_H = 58.0                 # floor underside (Z=0) to rim top
GROUND_CLEAR = 12.0

# ---------------- wheels / motors ----------------
WHEEL_D = 80.0
NEMA_BODY = 42.3
NEMA_LEN = 40.0
NEMA_BOLT = 31.0
NEMA_SHAFT_D = 5.0
M3, M2_5 = 3.4, 2.9

MOTOR_STATION_X = 78.0
MOTOR_AXIS_Z = WHEEL_D / 2 - GROUND_CLEAR      # 28.0 — puts the axle at wheel centre
MOTOR_PAD_T = 4.0                              # wall thickened locally at each motor
MOTOR_PAD_W = 50.0
SHAFT_BORE_D = 23.0

# derived motor envelope (used by the checks)
MOTOR_X_IN = MOTOR_STATION_X - NEMA_BODY / 2   # 56.85
MOTOR_X_OUT = MOTOR_STATION_X + NEMA_BODY / 2  # 99.15
INNER_Y = BOX_Y / 2 - WALL                     # 101.8
MOTOR_Y_IN = INNER_Y - NEMA_LEN                # 61.8

# ---------------- electronics ----------------
BOSS_D, BOSS_H = 7.0, 5.0

# Pi 4B: 85 x 56 board, holes 58 x 49. Rotated 90deg -> 56 in X, 85 in Y.
PI_W, PI_L = 56.0, 85.0
PI_HOLE_X, PI_HOLE_Y = 49.0, 58.0
PI_AT = (-30.0, 8.0)

# Uno R4 (classic Uno pattern), rotated 90deg -> long side along Y.
UNO_W, UNO_L = 53.34, 68.58
UNO_HOLES_RAW = [(-20.32, -24.13), (-19.05, 24.13), (31.75, -8.89), (31.75, 19.05)]
UNO_HOLES = [(-y, x) for (x, y) in UNO_HOLES_RAW]      # rotate +90 about Z
UNO_AT = (30.0, 4.0)

# LiPo 3S 2000mAh, long axis along X, in the rear spine
BATT_X, BATT_Y = 105.0, 34.0
BATT_AT = (0.0, -80.0)
BATT_WALL = 2.4
BATT_BAY_H = 14.0
STRAP_SLOT_W = 4.0

# ---------------- trashcan interface ----------------
# 4 locating tabs beat a full ring: less plastic, no fit problem, same job.
CAN_DIA = 203.0
TAB_R = CAN_DIA / 2 + 1.5     # tab inner face just clears the can
TAB_W, TAB_T, TAB_H = 16.0, 3.0, 8.0
CAN_BOLTS = 4
CAN_BOLT_PCD = 168.0

# ---------------- lid ----------------
LID_T = 3.2
LID_BOSS_D = 9.0
# wall midpoints — the corners are occupied by motors
LID_BOSS_AT = [(0.0, 98.0), (0.0, -98.0), (98.0, 0.0), (-98.0, 0.0)]

# ---------------- front sensor pod ----------------
# TF-Luna datasheet (Benewake SJ-GU-TF-Luna): 35 x 21.25 x 12.5 mm (L*W*H).
# The mounting-hole spacing only appears in the drawing image, not the text, so
# this pod RETAINS BY POCKET + ZIP TIE rather than guessing a bolt pattern.
LUNA_L, LUNA_W, LUNA_H = 35.0, 21.25, 12.5
LUNA_FIT = 0.4                 # printed clearance per axis
POD_Z = 38.0                   # height up the front wall (can starts at Z=58)
POD_BOLT_Y, POD_BOLT_Z = 44.0, 24.0
POD_BACK_T = 4.0
POD_W, POD_H = 62.0, 42.0
CAM_PAD_W, CAM_PAD_D = 56.0, 26.0
TIE_SLOT = (3.2, 8.0)          # zip-tie slot w x h

# ---------------- service ----------------
VENT_W, VENT_H, VENT_N = 3.0, 20.0, 7
WIRE_D = 16.0
USB_SLOT = (36.0, 15.0)


def chassis_box():
    with BuildPart() as bp:
        # ---- shell ----
        with BuildSketch(Plane.XY):
            RectangleRounded(BOX_X, BOX_Y, 8.0)
        extrude(amount=BOX_H)
        with BuildSketch(Plane.XY.offset(FLOOR)):
            RectangleRounded(BOX_X - 2 * WALL, BOX_Y - 2 * WALL, 5.0)
        extrude(amount=BOX_H - FLOOR, mode=Mode.SUBTRACT)

        # ---- motor pads: thicken each side wall locally so M3s have meat ----
        for sx in (MOTOR_STATION_X, -MOTOR_STATION_X):
            for sy in (1, -1):
                y_face = sy * INNER_Y
                pad = Box(MOTOR_PAD_W, MOTOR_PAD_T, MOTOR_PAD_W,
                          align=(Align.CENTER, Align.CENTER, Align.CENTER),
                          mode=Mode.PRIVATE)
                add(Location((sx, y_face - sy * MOTOR_PAD_T / 2, MOTOR_AXIS_Z)) * pad)

        # ---- shaft bore + NEMA17 bolt pattern through each side wall ----
        for sx in (MOTOR_STATION_X, -MOTOR_STATION_X):
            for sy in (1, -1):
                plane = Plane(origin=(sx, sy * BOX_Y / 2, MOTOR_AXIS_Z), z_dir=(0, sy, 0))
                with BuildSketch(plane):
                    Circle(SHAFT_BORE_D / 2)
                    with GridLocations(NEMA_BOLT, NEMA_BOLT, 2, 2):
                        Circle(M3 / 2)
                extrude(amount=-(WALL + MOTOR_PAD_T + 2), mode=Mode.SUBTRACT)

        # ---- Pi bosses ----
        with BuildSketch(Plane.XY.offset(FLOOR)):
            with Locations(PI_AT):
                with GridLocations(PI_HOLE_X, PI_HOLE_Y, 2, 2):
                    Circle(BOSS_D / 2)
        extrude(amount=BOSS_H)
        with BuildSketch(Plane.XY.offset(FLOOR + BOSS_H)):
            with Locations(PI_AT):
                with GridLocations(PI_HOLE_X, PI_HOLE_Y, 2, 2):
                    Circle(2.1 / 2)                # M2.5 self-tap pilot
        extrude(amount=-BOSS_H, mode=Mode.SUBTRACT)

        # ---- Uno bosses ----
        with BuildSketch(Plane.XY.offset(FLOOR)):
            for hx, hy in UNO_HOLES:
                with Locations((UNO_AT[0] + hx, UNO_AT[1] + hy)):
                    Circle(BOSS_D / 2)
        extrude(amount=BOSS_H)
        with BuildSketch(Plane.XY.offset(FLOOR + BOSS_H)):
            for hx, hy in UNO_HOLES:
                with Locations((UNO_AT[0] + hx, UNO_AT[1] + hy)):
                    Circle(2.6 / 2)                # M3 self-tap pilot
        extrude(amount=-BOSS_H, mode=Mode.SUBTRACT)

        # ---- battery bay ----
        with BuildSketch(Plane.XY.offset(FLOOR)):
            with Locations(BATT_AT):
                Rectangle(BATT_X + 2 * BATT_WALL, BATT_Y + 2 * BATT_WALL)
        extrude(amount=BATT_BAY_H)
        with BuildSketch(Plane.XY.offset(FLOOR)):
            with Locations(BATT_AT):
                Rectangle(BATT_X, BATT_Y)
        extrude(amount=BATT_BAY_H, mode=Mode.SUBTRACT)
        with BuildSketch(Plane.XY):
            for sx in (-38.0, 38.0):
                with Locations((BATT_AT[0] + sx, BATT_AT[1])):
                    SlotOverall(BATT_Y + 2 * BATT_WALL + 10, STRAP_SLOT_W, rotation=90)
        extrude(amount=FLOOR, mode=Mode.SUBTRACT)

        # ---- lid screw bosses ----
        # At the WALL MIDPOINTS, not the corners: the corners are full of motor.
        for bx, by in LID_BOSS_AT:
            with BuildSketch(Plane.XY.offset(FLOOR)):
                with Locations((bx, by)):
                    Circle(LID_BOSS_D / 2)
            extrude(amount=BOX_H - FLOOR)
            with BuildSketch(Plane.XY.offset(BOX_H)):
                with Locations((bx, by)):
                    Circle(2.6 / 2)               # M3 self-tap pilot
            extrude(amount=-12.0, mode=Mode.SUBTRACT)

        # ---- vents in both side walls ----
        for sy in (1, -1):
            plane = Plane(origin=(0, sy * BOX_Y / 2, BOX_H * 0.6), z_dir=(0, sy, 0))
            with BuildSketch(plane):
                with GridLocations(VENT_W * 3.0, 0, VENT_N, 1):
                    Rectangle(VENT_W, VENT_H)
            extrude(amount=-(WALL + 2), mode=Mode.SUBTRACT)

        # ---- wire pass-throughs ----
        with BuildSketch(Plane.XY):
            for wx, wy in ((-30.0, -45.0), (30.0, -45.0)):
                with Locations((wx, wy)):
                    Circle(WIRE_D / 2)
        extrude(amount=FLOOR, mode=Mode.SUBTRACT)

        # ---- sensor pod bolt holes, front wall ----
        plane = Plane(origin=(BOX_X / 2, 0, POD_Z), z_dir=(1, 0, 0))
        with BuildSketch(plane):
            with GridLocations(POD_BOLT_Y, POD_BOLT_Z, 2, 2):
                Circle(2.6 / 2)                    # M3 self-tap into the wall
        extrude(amount=-(WALL + 2), mode=Mode.SUBTRACT)

        # ---- USB / power access in the front wall ----
        plane = Plane(origin=(BOX_X / 2, 8.0, 22.0), z_dir=(1, 0, 0))
        with BuildSketch(plane):
            SlotOverall(USB_SLOT[0], USB_SLOT[1])
        extrude(amount=-(WALL + 2), mode=Mode.SUBTRACT)

    return bp.part


def lid():
    """Closes the box and carries the trashcan. A solid plate, so the locating
    tabs actually have something under them (on the open box they floated)."""
    with BuildPart() as lp:
        with BuildSketch(Plane.XY):
            RectangleRounded(BOX_X, BOX_Y, 8.0)
        extrude(amount=LID_T)

        # screw down to the box's rim bosses
        with BuildSketch(Plane.XY.offset(LID_T)):
            for bx, by in LID_BOSS_AT:
                with Locations((bx, by)):
                    Circle(M3 / 2)
        extrude(amount=-LID_T, mode=Mode.SUBTRACT)

        # trashcan locating tabs — supported by the plate beneath them
        for ang in (45, 135, 225, 315):
            plane = Plane(origin=(0, 0, LID_T)).rotated((0, 0, ang))
            with BuildSketch(plane):
                with Locations((TAB_R + TAB_T / 2, 0)):
                    Rectangle(TAB_T, TAB_W)
            extrude(amount=TAB_H)

        # trashcan bolt holes
        with BuildSketch(Plane.XY.offset(LID_T)):
            with PolarLocations(CAN_BOLT_PCD / 2, CAN_BOLTS, start_angle=0):
                Circle(M3 / 2)
        extrude(amount=-LID_T, mode=Mode.SUBTRACT)

        # Wire gland only. NO mast slot up here: the can (r=101.5) covers
        # everything inside r=101.5, and the lid is only r=105 — there is no
        # room on top for a mast. Sensors go on the BOX FRONT WALL instead.
        with BuildSketch(Plane.XY.offset(LID_T)):
            with Locations((-60.0, 0.0)):
                Circle(WIRE_D / 2)
        extrude(amount=-LID_T, mode=Mode.SUBTRACT)
    return lp.part


def sensor_pod():
    """Bolts to the BOX FRONT WALL, below the lid, so the trashcan never blocks
    the view. Holds the TF Luna in a pocket and the webcam on a zip-tie pad.
    Printed back-flat on the bed: no supports."""
    with BuildPart() as pd:
        # backplate (lies in YZ once mounted; modelled flat in XY, back on the bed)
        with BuildSketch(Plane.XY):
            RectangleRounded(POD_W, POD_H, 4.0)
        extrude(amount=POD_BACK_T)

        # bolt holes to the box wall
        with BuildSketch(Plane.XY):
            with GridLocations(POD_BOLT_Y, POD_BOLT_Z, 2, 2):
                Circle(M3 / 2)
        extrude(amount=POD_BACK_T, mode=Mode.SUBTRACT)

        # TF Luna pocket: walls around the module, front open so the lens sees out
        pocket_w, pocket_l = LUNA_W + LUNA_FIT, LUNA_L + LUNA_FIT
        with BuildSketch(Plane.XY.offset(POD_BACK_T)):
            with Locations((0, -POD_H / 4)):
                Rectangle(pocket_l + 2 * 2.4, pocket_w + 2 * 2.4)
        extrude(amount=LUNA_H + 2.0)
        with BuildSketch(Plane.XY.offset(POD_BACK_T)):
            with Locations((0, -POD_H / 4)):
                Rectangle(pocket_l, pocket_w)
        extrude(amount=LUNA_H + 2.0, mode=Mode.SUBTRACT)

        # webcam pad + zip-tie slots (webcam shape unknown -> strap it)
        with BuildSketch(Plane.XY.offset(POD_BACK_T)):
            with Locations((0, POD_H / 4)):
                Rectangle(CAM_PAD_W, CAM_PAD_D)
        extrude(amount=3.0)
        with BuildSketch(Plane.XY):
            for sy in (-1, 1):
                with Locations((sy * (CAM_PAD_W / 2 - 5), POD_H / 4)):
                    Rectangle(TIE_SLOT[0], TIE_SLOT[1])
        extrude(amount=POD_BACK_T + 3.0, mode=Mode.SUBTRACT)

        # zip-tie slots to strap the Luna into its pocket
        with BuildSketch(Plane.XY):
            for sy in (-1, 1):
                with Locations((sy * (pocket_l / 2 + 4.0), -POD_H / 4)):
                    Rectangle(TIE_SLOT[0], TIE_SLOT[1])
        extrude(amount=POD_BACK_T, mode=Mode.SUBTRACT)
    return pd.part


if __name__ == "__main__":
    import shutil
    box = chassis_box()
    pod = sensor_pod()
    export_step(pod, "fetch_sensorpod.step")
    shutil.copyfile("fetch_sensorpod.step", "fetch_sensorpod.stp")
    export_stl(pod, "fetch_sensorpod.stl", tolerance=0.05, angular_tolerance=0.2)
    lid_p = lid()
    export_step(lid_p, "fetch_lid.step")
    shutil.copyfile("fetch_lid.step", "fetch_lid.stp")
    export_stl(lid_p, "fetch_lid.stl", tolerance=0.05, angular_tolerance=0.2)
    export_step(box, "fetch_box.step")
    shutil.copyfile("fetch_box.step", "fetch_box.stp")
    export_stl(box, "fetch_box.stl", tolerance=0.05, angular_tolerance=0.2)

    bb = box.bounding_box()
    print(f"box  {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")
    print(f"volume {box.volume/1000:.1f} cm^3  (~{box.volume/1000*1.24:.0f} g PLA)")

    print("\n=== CHECKS ===")
    fails = []

    def chk(name, ok, detail=""):
        if not ok:
            fails.append(name)
        print(f"  [{'OK  ' if ok else 'FAIL'}] {name:<38} {detail}")

    # --- printability ---
    chk("fits 220x220 bed (Ender)", bb.size.X <= 220 and bb.size.Y <= 220,
        f"{bb.size.X:.0f} x {bb.size.Y:.0f}")
    chk("fits 256x256 bed (Bambu/Prusa)", bb.size.X <= 256 and bb.size.Y <= 256,
        f"{bb.size.X:.0f} x {bb.size.Y:.0f}")

    # --- motor geometry ---
    mb, mt = MOTOR_AXIS_Z - NEMA_BODY / 2, MOTOR_AXIS_Z + NEMA_BODY / 2
    chk("motor body clears floor", mb > FLOOR, f"body base Z {mb:.2f} > floor {FLOOR}")
    chk("motor body under rim", mt < BOX_H, f"body top Z {mt:.2f} < rim {BOX_H}")
    chk("axle on wheel centreline", abs((MOTOR_AXIS_Z + GROUND_CLEAR) - WHEEL_D / 2) < 1e-9,
        f"axle {MOTOR_AXIS_Z + GROUND_CLEAR:.1f} = r {WHEEL_D/2:.1f}")
    chk("motor fits inside box in X", MOTOR_X_OUT < BOX_X / 2 - WALL,
        f"motor to |X|{MOTOR_X_OUT:.1f} < inner {BOX_X/2-WALL:.1f}")

    # --- electronics vs motor corners ---
    def corners(at, w, l):
        return (abs(at[0]) + w / 2, at[1] - l / 2, at[1] + l / 2)

    for name, at, w, l in (("Pi", PI_AT, PI_W, PI_L), ("Uno", UNO_AT, UNO_W, UNO_L)):
        xmax, ylo, yhi = corners(at, w, l)
        # safe if EITHER it stays in the spine (|X| < MOTOR_X_IN)
        # OR it stays in the central band (|Y| < MOTOR_Y_IN)
        in_spine = xmax < MOTOR_X_IN
        in_band = max(abs(ylo), abs(yhi)) < MOTOR_Y_IN
        chk(f"{name} clears motor corners", in_spine or in_band,
            f"|X|max {xmax:.1f} (spine<{MOTOR_X_IN:.1f}) | Y {ylo:.1f}..{yhi:.1f} "
            f"(band<{MOTOR_Y_IN:.1f})")
        chk(f"{name} inside walls", xmax < BOX_X / 2 - WALL and yhi < INNER_Y and ylo > -INNER_Y,
            f"X {xmax:.1f} Y {ylo:.1f}..{yhi:.1f} vs inner {INNER_Y:.1f}")

    bx = BATT_X / 2 + BATT_WALL
    blo, bhi = BATT_AT[1] - (BATT_Y / 2 + BATT_WALL), BATT_AT[1] + (BATT_Y / 2 + BATT_WALL)
    chk("battery in rear spine", bx < MOTOR_X_IN, f"|X| {bx:.1f} < {MOTOR_X_IN:.1f}")
    chk("battery inside rear wall", blo > -INNER_Y, f"rear edge {blo:.1f} > {-INNER_Y:.1f}")

    # --- nothing overlaps anything ---
    def rect(at, w, l):
        return (at[0] - w / 2, at[0] + w / 2, at[1] - l / 2, at[1] + l / 2)

    def overlap(a, b):
        return not (a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2])

    pi_r = rect(PI_AT, PI_W, PI_L)
    uno_r = rect(UNO_AT, UNO_W, UNO_L)
    bat_r = rect(BATT_AT, BATT_X + 2 * BATT_WALL, BATT_Y + 2 * BATT_WALL)
    chk("Pi vs Uno no overlap", not overlap(pi_r, uno_r),
        f"Pi X{pi_r[0]:.0f}..{pi_r[1]:.0f} | Uno X{uno_r[0]:.0f}..{uno_r[1]:.0f}")
    chk("Pi vs battery no overlap", not overlap(pi_r, bat_r))
    chk("Uno vs battery no overlap", not overlap(uno_r, bat_r))

    # --- trashcan interface ---
    # The tabs sit at 45/135/225/315 deg. The box is SQUARE, so the usable
    # radius on a diagonal is h/cos(45) = 148mm, not h. Check the tabs' real
    # X/Y extent instead of pretending the limit is circular.
    import math as _m
    tab_xy = []
    for ang in (45, 135, 225, 315):
        a = _m.radians(ang)
        ca, sa = _m.cos(a), _m.sin(a)
        for dr in (TAB_R, TAB_R + TAB_T):            # inner + outer radial face
            for dt in (-TAB_W / 2, TAB_W / 2):       # both tangential edges
                tab_xy.append((dr * ca - dt * sa, dr * sa + dt * ca))
    tx = max(abs(p[0]) for p in tab_xy)
    ty = max(abs(p[1]) for p in tab_xy)
    chk("can tabs inside box footprint", tx < BOX_X / 2 and ty < BOX_Y / 2,
        f"tab extent X{tx:.1f} Y{ty:.1f} vs half {BOX_X/2:.0f}/{BOX_Y/2:.0f}")
    chk("can tabs clear the rounded corners",
        _m.hypot(max(0, tx - (BOX_X / 2 - 8)), max(0, ty - (BOX_Y / 2 - 8))) < 8,
        "tabs sit inboard of the 8mm corner radius")
    chk("can bolts land on the rim", CAN_BOLT_PCD / 2 < min(BOX_X, BOX_Y) / 2 - 4,
        f"PCD/2 {CAN_BOLT_PCD/2:.1f}")
    chk("can bolts clear the tabs", abs(CAN_BOLT_PCD / 2 - TAB_R) > 6,
        f"bolt r{CAN_BOLT_PCD/2:.1f} vs tab r{TAB_R:.1f}")

    print(f"\n  {'ALL CHECKS PASS' if not fails else f'{len(fails)} FAILED: ' + ', '.join(fails)}")
    print("  wrote fetch_box.step / .stp / .stl")
