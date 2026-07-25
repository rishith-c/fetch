"""
FETCH — shaft coupler.  5mm NEMA female  ->  HEX male (for mecanum wheel).

Adapts the JK42HS40-1704-13A (NEMA 17, 5mm D-cut shaft) to the HEXAGONAL hole
in the common yellow-and-black plastic mecanum wheels (e.g. DFRobot 80mm
FIT0654, spec "Hex Hole 7*7*7mm"). The wheel's hub is a hex socket, not a round
bore, so the coupler's output is a hexagonal male prism that drops into it —
the six hex faces ARE the drive; there is no separate flat to cut.

    #########################################################################
    ##  IF THE WHEEL IS LOOSE OR WON'T GO ON: measure YOUR wheel's hex     ##
    ##  hole ACROSS THE FLATS with calipers and set HEX_AF below to that   ##
    ##  number. That single value is the whole fit. Everything else stays. ##
    #########################################################################

PRINT IT STANDING UP (axis vertical, boss up), 4 walls, 40%+ infill.
    Torsion on this part shears the layer planes — the weak direction.
    Standing up + 4 walls puts solid perimeter loops around the bore and the
    hex boss, which is what actually carries the torque.

TOLERANCES — the whole point of this part
    FDM prints holes UNDERSIZE and bosses OVERSIZE. Both errors eat clearance,
    so they are compensated in opposite directions:
        bore    5.0 nominal -> 5.3 modelled   (+0.30 so it comes out ~5.0-5.1)
        hex_af  7.0 nominal -> 6.70 modelled   (-0.30 so it slides into the hex)
    Those offsets are tuned for a typical 0.4mm nozzle / 0.2mm layer PLA.
    A proven community adaptor for this exact 80mm DFRobot wheel models the
    inserted hex at 6.5mm AF; if 6.70 prints tight, drop HEX_FIT toward -0.5.

THE D-FLAT (motor side) IS NOT OPTIONAL
    A round bore on a round shaft slips under load. The 5mm NEMA shaft has a
    D-cut; this bore matches it, and that flat is what transmits the torque on
    the motor side. The grub screw only stops axial pull-out — it is not drive.

COORDINATES
    origin = centre of the part, on the FEMALE (motor) end face, Z=0
    +Z = away from the motor, out toward the wheel.
"""
from build123d import *

# ---------------------------------------------------------------- motor side
SHAFT_D      = 5.0    # JK42HS40-1704-13A shaft diameter
SHAFT_FLAT   = 4.5    # across the D-cut (0.5mm flat, the NEMA standard)
BORE_FIT     = 0.30   # printed holes come out small — open it up
BORE_DEPTH   = 18.0   # shaft is 22mm usable; 18 leaves room and a solid floor

# ================================================================ WHEEL SIDE
# HEX_AF is the ONE number that decides whether the wheel fits. It is the
# across-flats size of the wheel's HEX HOLE. 7.0mm is the DFRobot 80mm wheel
# ("Hex Hole 7*7*7mm"); other common yellow/black wheels run 6.0-6.7mm.
#   ->  MEASURE YOUR wheel's hex hole across the flats and put it here.  <-
HEX_AF       = 8.0    # nominal across-flats of the wheel's hex socket (mm)
HEX_FIT      = -0.30  # boss prints fat + needs slide clearance -> shrink it
HEX_LEN      = 15.0   # how far the boss reaches into the wheel hub
# ===========================================================================

# ---------------------------------------------------------------- body
BODY_D       = 16.0
BODY_LEN     = 20.0   # > BORE_DEPTH, so there is a floor under the shaft
GRUB_PILOT   = 2.5    # M3 self-tapping into plastic (NOT 3.4 clearance)
CHAMFER      = 0.6
HEX_TIP_CH   = 0.5    # lead-in on the hex tip so it starts into the hole

bore_d  = SHAFT_D + BORE_FIT           # 5.30
bore_f  = SHAFT_FLAT + BORE_FIT        # 4.80
hex_af  = HEX_AF + HEX_FIT             # 6.70 modelled across-flats


def flat_cut(dia, across_flat, rect_h):
    """Centre for a rect that trims a dia-cylinder down to `across_flat`.

    A D-profile is circle INTERSECT halfplane — the circle gets trimmed DOWN.
    Cutting a rectangle that merely sits beside the circle gives you
    circle UNION rectangle, which is a different and much worse shape.
    """
    return -dia / 2 + across_flat + rect_h / 2


BORE_FLAT_Y = -bore_d / 2 + bore_f     # +2.15 — the face the shaft flat sits on
GRUB_DEPTH  = BODY_D / 2 - BORE_FLAT_Y + 0.5

with BuildPart() as coupler:
    # body — the collar that clamps the motor shaft
    Cylinder(BODY_D / 2, BODY_LEN, align=(Align.CENTER, Align.CENTER, Align.MIN))

    # output boss — a HEX PRISM. Extruding a hexagon sketch makes the boss a
    # hexagon BY CONSTRUCTION (six flats, no subtraction), so it can never come
    # out as a fin. major_radius=False means `radius` is the apothem, so
    # flat-to-flat = hex_af exactly. rotation=0 -> flats face +/-Y, corners +/-X.
    with BuildSketch(Plane.XY.offset(BODY_LEN)):
        RegularPolygon(hex_af / 2, side_count=6, major_radius=False)
    extrude(amount=HEX_LEN)

    # chamfer the collar bottom — kills the elephant foot (a circle edge)
    bottom = coupler.edges().filter_by(GeomType.CIRCLE).group_by(Axis.Z)[0]
    chamfer(bottom, CHAMFER)

    # lead-in on the hex tip: chamfer the 6 edges of the topmost (hex) face.
    # A regular hexagon's edges are 6 clean lines meeting at 6 corners — unlike
    # a D-profile (arc + line) this chamfers fine.
    hex_top = coupler.faces().filter_by(Axis.Z).group_by(Axis.Z)[-1]
    chamfer(hex_top.edges(), HEX_TIP_CH)

    # the D-bore (motor side, UNCHANGED). Trim the circle to a D IN THE SKETCH,
    # then subtract once — cavity is circle INTERSECT halfplane, not union.
    h = bore_d * 2
    with BuildSketch(Plane.XY) as dbore:
        Circle(bore_d / 2)
        with Locations((0, flat_cut(bore_d, bore_f, h))):
            Rectangle(h, h, mode=Mode.SUBTRACT)
    extrude(amount=BORE_DEPTH, mode=Mode.SUBTRACT)

    # lead-in on the bore mouth as a cone (does not care that the mouth is a D).
    with Locations((0, 0, 0)):
        Cone(bore_d / 2 + CHAMFER, bore_d / 2, CHAMFER,
             align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

    # Grub screw. Comes in from +Y — the side the shaft's flat faces. From -Y
    # it would press the round side and cam the coupler off-centre.
    with BuildSketch(Plane.XZ.offset(-BODY_D / 2)):
        with Locations((0, BORE_DEPTH * 0.55)):
            Circle(GRUB_PILOT / 2)
    extrude(amount=GRUB_DEPTH, mode=Mode.SUBTRACT)

part = coupler.part
part.label = "fetch_shaft_coupler_5mm_D_to_hex"


def gen_step():
    return part


if __name__ == "__main__":
    import math

    bb = part.bounding_box()
    print(f"bbox   {bb.size.X:.2f} x {bb.size.Y:.2f} x {bb.size.Z:.2f} mm")
    print(f"volume {part.volume/1000:.2f} cm^3")
    print(f"solids {len(part.solids())}   valid {part.is_valid}")
    print(f"hex across-flats modelled = {hex_af:.2f} mm  (nominal {HEX_AF} + fit {HEX_FIT})")

    # --- the checks that would actually cost you a reprint ---
    assert len(part.solids()) == 1, "must be ONE solid or the slicer guesses"
    assert part.is_valid, "not a valid B-rep"
    assert abs(bb.size.Z - (BODY_LEN + HEX_LEN)) < 1e-6, "length drifted"
    assert abs(bb.size.X - BODY_D) < 1e-6, "body is not the widest thing"

    # bore floor: shaft must bottom out on plastic, not punch through
    assert BODY_LEN - BORE_DEPTH >= 1.5, "floor under the shaft is too thin"

    # collar wall around the bore — this is what the grub screw pulls against
    wall = (BODY_D - bore_d) / 2
    assert wall >= 3.0, f"collar wall {wall:.2f}mm too thin"

    # motor-side D-flat must actually bite, or the coupler spins on the shaft
    assert bore_d - bore_f >= 0.4, "bore D-flat too shallow to drive"

    # --- shape probes -------------------------------------------------------
    # Dimensions cannot see a fin or a circle-that-should-be-a-hex. Points can.
    def is_solid(x, y, z, r=0.35):
        return (part & Sphere(r).locate(Location((x, y, z)))).volume > 1e-9

    a  = hex_af / 2                       # apothem   (flat @ this radius, +/-Y)
    rc = a / math.cos(math.radians(30))   # circumradius (corner, +/-X)
    zb = BODY_LEN + HEX_LEN / 2           # mid-boss

    # 1. boss is solid through the middle (not a fin, not a tube)
    assert is_solid(0, 0, zb), "boss centre is hollow"
    for k in range(12):                   # everything inside the apothem is solid
        ang = math.radians(k * 30)
        assert is_solid(a * 0.85 * math.cos(ang), a * 0.85 * math.sin(ang), zb), \
            "hole in the boss cross-section"

    # 2. boss is a HEXAGON, not a circle: at a radius between the apothem and the
    #    circumradius, the corner directions (+/-X) are solid but the flat
    #    directions (+/-Y) are void. A circle would be uniform.
    r_mid = (a + rc) / 2                  # 3.61: outside the flats, inside corners
    assert is_solid(+r_mid, 0, zb, 0.2) and is_solid(-r_mid, 0, zb, 0.2), \
        "hex corner missing"
    assert not is_solid(0, +r_mid, zb, 0.2) and not is_solid(0, -r_mid, zb, 0.2), \
        "flat direction is solid — boss is round, not hexagonal"
    assert not is_solid(0, a + 0.5, zb), "hex is oversize across the flats"

    # 3. measure the across-flats directly off a thin slab through the boss.
    slab = (part & Box(50, 50, 0.4).locate(Location((0, 0, zb)))).bounding_box()
    af_meas = min(slab.size.X, slab.size.Y)
    corner  = max(slab.size.X, slab.size.Y)
    assert abs(af_meas - hex_af) < 0.1, f"across-flats {af_meas:.2f} != {hex_af:.2f}"
    assert abs(corner - 2 * rc) < 0.1, "corner span wrong — not a regular hexagon"
    print(f"boss measured: {af_meas:.2f} mm across flats, {corner:.2f} mm across corners")

    # bore must be a D: material on the flat side, cavity on the round side
    assert is_solid(0, BORE_FLAT_Y + 0.45, 5.0), "flat side of bore is void"
    assert not is_solid(0, -2.0, 5.0), "round side of bore is solid"

    # grub screw enters on the side the shaft's flat FACES (+Y), not -Y
    zg = BORE_DEPTH * 0.55
    assert not is_solid(0, BODY_D / 2 - 1.5, zg), "grub screw is on the wrong side"
    assert is_solid(0, -BODY_D / 2 + 1.5, zg), "grub screw drilled straight through"

    # --- analytic volume ----------------------------------------------------
    def seg(r, c):
        return r * r * math.acos(c / r) - c * math.sqrt(r * r - c * c)

    a_hex  = (math.sqrt(3) / 2) * hex_af ** 2                       # regular hex
    a_bore = math.pi * (bore_d / 2) ** 2 - seg(bore_d / 2, -bore_d / 2 + bore_f)
    v_want = (math.pi * (BODY_D / 2) ** 2 * BODY_LEN               # collar
              + a_hex * HEX_LEN                                    # hex boss
              - a_bore * BORE_DEPTH                                # D bore
              - math.pi * (GRUB_PILOT / 2) ** 2 * GRUB_DEPTH)
    err = abs(part.volume - v_want) / v_want
    print(f"volume {part.volume:.0f} vs analytic {v_want:.0f} mm^3  ({err*100:.1f}% "
          f"— chamfers + lead-in cone account for the rest)")
    assert err < 0.02, f"volume off by {err*100:.1f}% — a feature came out wrong"

    # grub screw must break into the bore, and miss the floor
    assert BODY_D / 2 > bore_f - bore_d / 2, "grub screw misses the bore"
    assert BORE_DEPTH * 0.55 + GRUB_PILOT / 2 < BORE_DEPTH, "grub past bore end"

    # torsion. 17HS4401 holds 0.43 Nm; the hex boss is the thinnest section.
    # Model it conservatively as a round shaft of the inscribed (across-flats)
    # diameter — a real hexagon is stiffer, so this over-estimates the stress.
    T, d = 0.43, hex_af / 1000
    tau = 16 * T / (math.pi * d ** 3) / 1e6          # MPa
    assert tau < 8.0, f"boss torsional stress {tau:.1f} MPa too high"
    print(f"\nboss torsion {tau:.1f} MPa (conservative) vs ~25 MPa PLA layer shear "
          f"-> {25/tau:.1f}x margin (printed standing up)")
    print("all assertions passed")
