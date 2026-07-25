"""
FETCH — flat DECK.  Motors tape to the TOP.  Replaces fetch_box.py.

WHY THE MOTORS GO ON TOP AND NOT UNDERNEATH
    Tape holds well in shear, badly in peel. A motor sitting ON the deck puts
    its 280g into compression and the drive loads into shear — the directions
    tape is good at. Hung underneath, that same 280g is pure tension trying to
    peel the patch off, all the time, warm, vibrating. Same tape, opposite
    outcome. So: on top.

THE THING YOU ASKED ABOUT — will the wheels reach the ground?
    Yes, and the deck height is not a choice. Work it backwards:

        wheel axis must sit at exactly WHEEL_D/2 = 40mm  (or it isn't rolling)
        the axis sits MOTOR_SQ/2 = 21.15mm above whatever the motor rests on
        the motor rests on tape (1.0) on a pad (1.2) on the deck (4.0)

        deck underside = 40 - 21.15 - 1.0 - 1.2 - 4.0 = 12.65mm above ground

    That 12.65mm is your ground clearance, and it falls out of the geometry —
    there is no free parameter to get wrong. Thicken the deck and the robot
    just sits lower. The assertions at the bottom check it stays positive.

    The wheels are the ONLY things touching the floor. Nothing is under them:
    the deck stops at Y=+-87.5 and the wheel's inner face is at 104.5, so
    there is 20mm of air between the deck edge and the tyre. That gap is the
    coupler collar — see shaft_coupler.py.

HOW THE MOTORS LOCATE
    The perimeter rib is the jig. Each motor butts into a corner of it, which
    fixes both its X and its Y with no measuring. This matters more than it
    looks: tape gives you no second chance, and four motors that are not
    parallel make the robot curve no matter how good the firmware is. Push
    each one into its corner, THEN press it down.

PRINT
    200 x 175 x 52 — fits a 220 Ender bed and a 256 Bambu. Not an A1 mini.
    Flat on the bed, no supports. USE A BRIM: this is a wide thin plate and
    it will lift at the corners without one. ~4h at 0.3mm layers.
    Print it BEFORE the event. It is the long pole in the whole build.

COORDINATES
    origin = deck centre, Z=0 on the deck UNDERSIDE (what sits on the bed).
    +X = forward, +Y = left, +Z = up. Ground is at Z = -GROUND_CLEAR.
"""
from build123d import *
import math

# ---------------------------------------------------------------- rolling stock
WHEEL_D        = 80.0     # mecanum outside diameter
WHEEL_W        = 38.0
MOTOR_SQ       = 42.3     # NEMA 17 body cross-section
MOTOR_L        = 40.0     # JK42HS40 — the "40" is the body length
TAPE_T         = 1.0      # Gorilla double-sided, compressed
COUPLER_COLLAR = 20.0     # wheel inner face, outboard of the motor face

# ---------------------------------------------------------------- deck
DECK_X, DECK_Y = 200.0, 175.0
DECK_T         = 4.0      # 0.33mm sag under the can — stiff enough, see below
RIB_W, RIB_H   = 3.0, 8.0 # perimeter rib: motor jig + anti-warp + stiffener
PAD_H          = 1.2      # raised tape pad, exactly the motor footprint

# ---------------------------------------------------------------- trashcan
CAN_D     = 203.2         # 8 inch bottom
POST_D    = 14.0
CAN_GAP   = 3.5           # post tops ABOVE the motors, so the can rests on
                          # the posts only and never on the motor cases
POST_XY   = [(45, 75), (45, -75), (-45, 75), (-45, -75)]

# ---------------------------------------------------------------- fasteners
M3_PILOT   = 2.5          # self-tapping into plastic, NOT 3.4 clearance
M25_PILOT  = 2.1
BOSS_D     = 7.0
BOSS_H     = 4.0

# ---------------------------------------------------------------- derived
GROUND_CLEAR = WHEEL_D / 2 - (DECK_T + PAD_H + TAPE_T + MOTOR_SQ / 2)
PAD_X   = DECK_X / 2 - RIB_W - MOTOR_SQ / 2      # 75.85
PAD_Y   = DECK_Y / 2 - RIB_W - MOTOR_L / 2       # 64.50
MOTOR_FACE_Y = DECK_Y / 2 - RIB_W                # 84.50
WHEEL_IN_Y   = MOTOR_FACE_Y + COUPLER_COLLAR     # 104.50
MOTOR_TOP    = DECK_T + PAD_H + TAPE_T + MOTOR_SQ
POST_TOP     = MOTOR_TOP + CAN_GAP
POST_H       = POST_TOP - DECK_T

# Everything mounts on TOP, so the whole band |Y| < 44.5 is free across the
# full length — the motors only occupy the four corners. Pi and Uno go there
# end to end, battery behind them, posts outboard of all of it.
PI_HOLES  = [(x, y) for x in (-29.0, 29.0) for y in (-24.5, 24.5)]   # 58 x 49
PI_AT     = (-50.0, -8.0)
UNO_AT    = (55.0, -8.0)
BATT_AT   = (0.0, 42.0)

# lightening pockets: (cx, cy, w, h). Each sits BETWEEN its mount points, so
# nothing structural is removed. Verified against every boss/post/slot below.
LIGHTEN = [(-50.0, -8.0, 40.0, 30.0),    # inside the Pi's 4 bosses
           (55.0, -8.0, 50.0, 30.0),     # inside the Uno's 4 tie slots
           (0.0, 42.0, 55.0, 26.0)]      # between the battery strap slots

with BuildPart() as deck:
    # ---- base plate
    Box(DECK_X, DECK_Y, DECK_T, align=(Align.CENTER, Align.CENTER, Align.MIN))

    # ---- perimeter rib. Doubles as the motor jig at the four corners.
    with BuildSketch(Plane.XY.offset(DECK_T)):
        Rectangle(DECK_X, DECK_Y)
        Rectangle(DECK_X - 2 * RIB_W, DECK_Y - 2 * RIB_W, mode=Mode.SUBTRACT)
    extrude(amount=RIB_H)

    # ---- tape pads, exactly the motor footprint, butted into each rib corner
    with BuildSketch(Plane.XY.offset(DECK_T)):
        with Locations(*[(sx * PAD_X, sy * PAD_Y)
                         for sx in (-1, 1) for sy in (-1, 1)]):
            Rectangle(MOTOR_SQ, MOTOR_L)
    extrude(amount=PAD_H)

    # ---- trashcan posts
    with BuildSketch(Plane.XY.offset(DECK_T)):
        with Locations(*POST_XY):
            Circle(POST_D / 2)
    extrude(amount=POST_H)

    # ---- Pi 4B bosses (58 x 49 M2.5)
    with BuildSketch(Plane.XY.offset(DECK_T)):
        with Locations(*[(PI_AT[0] + x, PI_AT[1] + y) for x, y in PI_HOLES]):
            Circle(BOSS_D / 2)
    extrude(amount=BOSS_H)

    # ---- holes: posts and Pi bosses, drilled after the bosses exist
    with BuildSketch(Plane.XY):
        with Locations(*POST_XY):
            Circle(M3_PILOT / 2)
        with Locations(*[(PI_AT[0] + x, PI_AT[1] + y) for x, y in PI_HOLES]):
            Circle(M25_PILOT / 2)
    extrude(amount=POST_TOP, mode=Mode.SUBTRACT)

    # ---- Uno + shield: zip-tie slots, not bosses. The Uno's hole pattern is
    # irregular and the CNC shield sits over it anyway — a tie is faster and
    # you can get the board back out without a screwdriver.
    with BuildSketch(Plane.XY):
        for sx in (-1, 1):
            with Locations((UNO_AT[0] + sx * 34, UNO_AT[1] - 26),
                           (UNO_AT[0] + sx * 34, UNO_AT[1] + 26)):
                SlotOverall(11, 3.2, rotation=90)
    extrude(amount=DECK_T, mode=Mode.SUBTRACT)

    # ---- battery strap slots (velcro through the deck)
    with BuildSketch(Plane.XY):
        with Locations((BATT_AT[0] - 35, BATT_AT[1]),
                       (BATT_AT[0] + 35, BATT_AT[1])):
            SlotOverall(28, 4.0, rotation=90)
    extrude(amount=DECK_T, mode=Mode.SUBTRACT)

    # ---- lightening, UNDER the boards. The Pi stands on 4 bosses and the Uno
    # hangs from 4 zip ties, so the deck between those points carries nothing
    # and can be air. A 4mm plate is nearly all solid layers, so removed area
    # is removed print time — and print time is the long pole here.
    # Placed strictly between the mount points; LIGHTEN_OK below proves it.
    with BuildSketch(Plane.XY):
        for cx, cy, w, h in LIGHTEN:
            with Locations((cx, cy)):
                RectangleRounded(w, h, 6)
    extrude(amount=DECK_T, mode=Mode.SUBTRACT)

    # No cable pass-throughs: everything mounts on the TOP face now, so the
    # motor leads just run across the deck to the Uno. Nothing to route to.
    # (The first draft also had lightening holes out at the motor stations.
    #  Two Pi bosses landed on one and printed as loose floating islands.)

part = deck.part
part.label = "fetch_deck"


def gen_step():
    return part


if __name__ == "__main__":
    bb = part.bounding_box()
    print(f"deck      {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")
    print(f"volume    {part.volume/1000:.1f} cm^3")
    print(f"solids    {len(part.solids())}   valid {part.is_valid}")
    print(f"\nGROUND CLEARANCE  {GROUND_CLEAR:.2f} mm   <-- deck underside")
    print(f"wheel axis        {WHEEL_D/2:.2f} mm above ground (= wheel radius)")
    print(f"deck edge Y       {DECK_Y/2:.1f}      wheel inner face Y {WHEEL_IN_Y:.1f}")
    print(f"air between them  {WHEEL_IN_Y - DECK_Y/2:.1f} mm — no plastic under any wheel")
    print(f"overall width     {2*(WHEEL_IN_Y + WHEEL_W):.0f} mm over the tyres")

    def is_solid(x, y, z, r=0.6):
        return (part & Sphere(r).locate(Location((x, y, z)))).volume > 1e-9

    assert len(part.solids()) == 1, "must print as ONE solid"
    assert part.is_valid, "not a valid B-rep"

    # --- the question that started this: do the wheels reach the floor? ---
    assert GROUND_CLEAR > 8.0, (
        f"ground clearance {GROUND_CLEAR:.1f}mm — deck would drag")
    assert WHEEL_IN_Y > DECK_Y / 2, "DECK EXTENDS UNDER THE WHEELS"
    assert WHEEL_IN_Y - DECK_Y / 2 >= 10.0, "too little air beside the tyre"

    # nothing on the deck may hang below the wheel contact patch
    assert bb.min.Z >= 0, "geometry below the deck underside"

    # --- trashcan vs wheels. The can is 203mm and the wheels stick out past
    # it, so the ONLY thing keeping them apart is radius. Check the wheel
    # corner that comes closest to the can axis.
    r_wheel = math.hypot(PAD_X - WHEEL_D / 2, WHEEL_IN_Y)
    can_gap = r_wheel - CAN_D / 2
    print(f"\ncan vs wheel      {can_gap:.1f} mm radial clearance")
    assert can_gap >= 6.0, (
        f"trashcan would foul the wheel tops by {-can_gap:.1f}mm — widen DECK_Y")

    # --- trashcan sits on posts ONLY, never on the motor cases
    assert POST_TOP > MOTOR_TOP, "can would rest on the motors"
    for px, py in POST_XY:
        assert abs(px) + POST_D / 2 < PAD_X - MOTOR_SQ / 2, "post fouls a motor"
        assert math.hypot(px, py) < CAN_D / 2 - 5, "post outside the can footprint"
    assert is_solid(POST_XY[0][0] + 5, POST_XY[0][1], DECK_T + POST_H - 2), \
        "post did not build"

    # --- pads and rib actually exist where the motor goes
    assert is_solid(PAD_X, PAD_Y, DECK_T + PAD_H - 0.3), "tape pad missing"
    assert is_solid(DECK_X / 2 - RIB_W / 2, PAD_Y, DECK_T + RIB_H - 1), \
        "rib missing — motors would have nothing to butt against"
    reg = RIB_H - PAD_H - TAPE_T
    assert reg >= 4.0, f"rib only registers {reg:.1f}mm of motor — too shallow"
    print(f"rib registers     {reg:.1f} mm of each motor body")

    # --- every mount must sit on real material, and nothing may overlap.
    # The first draft floated two Pi bosses over a lightening hole; it built,
    # it was "valid", and it would have printed as loose islands. Only the
    # solid count caught it, so the footprints are now checked explicitly.
    def boxes_hit(a, b):
        (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = a, b
        return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1

    def rect(cx, cy, w, h):
        return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

    mounts = {"Pi": rect(*PI_AT, 85, 56), "Uno": rect(*UNO_AT, 68.6, 53.4),
              "battery": rect(*BATT_AT, 105, 35)}
    pads = {f"motor{i}": rect(sx * PAD_X, sy * PAD_Y, MOTOR_SQ, MOTOR_L)
            for i, (sx, sy) in enumerate([(a, b) for a in (-1, 1) for b in (-1, 1)])}
    posts = {f"post{i}": rect(px, py, POST_D, POST_D)
             for i, (px, py) in enumerate(POST_XY)}

    zones = {**mounts, **pads, **posts}
    names = list(zones)
    for i, n in enumerate(names):
        for m in names[i + 1:]:
            assert not boxes_hit(zones[n], zones[m]), f"{n} overlaps {m}"
    for n, (x0, y0, x1, y1) in mounts.items():
        assert (max(abs(x0), abs(x1)) <= DECK_X / 2 - RIB_W and
                max(abs(y0), abs(y1)) <= DECK_Y / 2 - RIB_W), f"{n} hits the rib"
    print(f"layout            {len(zones)} footprints, no overlaps")

    # --- lightening must not undercut anything that carries load. Every boss,
    # post and tie slot needs >=3mm of solid deck all round it.
    MARGIN = 3.0
    carriers = {f"pi_boss{i}": (PI_AT[0] + x, PI_AT[1] + y, BOSS_D, BOSS_D)
                for i, (x, y) in enumerate(PI_HOLES)}
    carriers.update({f"post{i}": (px, py, POST_D, POST_D)
                     for i, (px, py) in enumerate(POST_XY)})
    for i, sx in enumerate((-1, 1)):
        for j, sy in enumerate((-1, 1)):
            carriers[f"unotie{i}{j}"] = (UNO_AT[0] + sx * 34,
                                         UNO_AT[1] + sy * 26, 3.2, 11)
    for k, s in enumerate((-1, 1)):
        carriers[f"strap{k}"] = (BATT_AT[0] + s * 35, BATT_AT[1], 4.0, 28)

    for hn, (hx, hy, hw, hh) in enumerate(LIGHTEN):
        hole = rect(hx, hy, hw + 2 * MARGIN, hh + 2 * MARGIN)
        for cn, (cx, cy, cw, ch) in carriers.items():
            assert not boxes_hit(hole, rect(cx, cy, cw, ch)), \
                f"lightening pocket {hn} undercuts {cn}"
    saved = sum(w * h for _, _, w, h in LIGHTEN) * DECK_T / 1000
    print(f"lightening        {len(LIGHTEN)} pockets, ~{saved:.0f} cm^3 of "
          f"plastic and print time saved, {MARGIN:.0f}mm clear of every mount")

    # --- will the tape actually hold? Motor torque reacts through the patch.
    TAPE_SHEAR_KPA = 50.0          # Gorilla heavy-duty ~30lb / 4 sq in
    patch = MOTOR_SQ * MOTOR_L
    force = 0.43 / (MOTOR_SQ / 2 / 1000)          # 0.43 Nm at 17HS4401 stall
    tau = force / patch * 1000                     # kPa
    print(f"tape shear        {tau:.0f} kPa of ~{TAPE_SHEAR_KPA:.0f} kPa "
          f"-> {TAPE_SHEAR_KPA/tau:.1f}x margin at STALL torque")
    assert TAPE_SHEAR_KPA / tau >= 2.0, "tape margin too thin"

    # --- deck sag under the can, motors as supports
    span, load = 2 * PAD_X, 15.0
    I = DECK_Y * DECK_T ** 3 / 12
    sag = load * span ** 3 / (48 * 3500 * I)
    print(f"deck sag          {sag:.2f} mm under 1.5kg centred")
    assert sag < 1.0, f"deck sags {sag:.1f}mm — thicken DECK_T"

    assert bb.size.X <= 220 and bb.size.Y <= 220, "will not fit a 220 bed"
    print("\nall assertions passed")
