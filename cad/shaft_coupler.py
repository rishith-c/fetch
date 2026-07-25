"""
FETCH — shaft coupler.  5mm NEMA female  ->  7mm male.

Adapts the JK42HS40-1704-13A (NEMA 17, 5mm D-cut shaft) to a 7mm wheel bore.

PRINT IT STANDING UP (axis vertical, boss up), 4 walls, 40%+ infill.
    Torsion on this part shears the layer planes — the weak direction.
    Standing up + 4 walls puts solid perimeter loops around both bores,
    which is what actually carries the torque. See the margin note below.

TOLERANCES — the whole point of this part
    FDM prints holes UNDERSIZE and bosses OVERSIZE. Both errors eat clearance,
    so they are compensated in opposite directions:
        bore  5.0 nominal -> 5.3 modelled   (+0.30 so it comes out ~5.0-5.1)
        boss  7.0 nominal -> 6.85 modelled  (-0.15 so it comes out ~6.95-7.05)
    Those offsets are tuned for a typical 0.4mm nozzle / 0.2mm layer PLA.
    If it is tight, bump BORE_FIT / drop BOSS_FIT by 0.05 and reprint — the
    part is 20 minutes, don't ream it.

THE D-FLAT IS NOT OPTIONAL
    A round bore on a round shaft slips under load. It will spin, polish
    itself, and then never grip again. The 5mm NEMA shaft has a D-cut; this
    bore matches it, and that flat is what transmits the torque. The grub
    screw only stops axial pull-out — it is not the drive.

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

# ---------------------------------------------------------------- wheel side
BOSS_D       = 7.0    # what the wheel bore wants
BOSS_FIT     = -0.15  # printed bosses come out fat — shrink it
BOSS_LEN     = 15.0
BOSS_FLAT_D  = 6.2    # flat on the output too: free grip for the wheel's grub

# ---------------------------------------------------------------- body
BODY_D       = 16.0
BODY_LEN     = 20.0   # > BORE_DEPTH, so there is a floor under the shaft
GRUB_PILOT   = 2.5    # M3 self-tapping into plastic (NOT 3.4 clearance)
CHAMFER      = 0.6

bore_d  = SHAFT_D + BORE_FIT           # 5.30
bore_f  = SHAFT_FLAT + BORE_FIT        # 4.80
boss_d  = BOSS_D + BOSS_FIT            # 6.85


def flat_cut(dia, across_flat, rect_h):
    """Centre for a rect that trims a dia-cylinder down to `across_flat`.

    A D-profile is circle INTERSECT halfplane — the circle gets trimmed DOWN.
    Cutting a rectangle that merely sits beside the circle gives you
    circle UNION rectangle, which is a different and much worse shape.
    The flat lands at y = -dia/2 + across_flat; everything above it goes.
    """
    return -dia / 2 + across_flat + rect_h / 2


BORE_FLAT_Y = -bore_d / 2 + bore_f     # +2.15 — the face the shaft flat sits on
GRUB_DEPTH  = BODY_D / 2 - BORE_FLAT_Y + 0.5

# Order matters: chamfer the round stock FIRST, then cut the flats. Chamfering
# a D-shaped edge (arc + line, two sharp corners) makes OCC give up.
with BuildPart() as coupler:
    # body — the collar that clamps the motor shaft
    Cylinder(BODY_D / 2, BODY_LEN, align=(Align.CENTER, Align.CENTER, Align.MIN))

    # output boss
    with Locations((0, 0, BODY_LEN)):
        Cylinder(boss_d / 2, BOSS_LEN, align=(Align.CENTER, Align.CENTER, Align.MIN))

    rings = coupler.edges().filter_by(GeomType.CIRCLE).group_by(Axis.Z)
    chamfer(rings[0], CHAMFER)   # bottom of the collar — kills the elephant foot
    chamfer(rings[-1], 0.4)      # boss tip — lead-in for the wheel bore

    # flat on the output boss — gives the wheel's grub screw something to bite.
    # A shaft with a flat still drops into a round bore, so this costs nothing.
    h = boss_d * 2
    with BuildSketch(Plane.XY.offset(BODY_LEN)):
        with Locations((0, flat_cut(boss_d, BOSS_FLAT_D, h))):
            Rectangle(h, h)
    extrude(amount=BOSS_LEN, mode=Mode.SUBTRACT)

    # the D-bore. Trim the circle to a D IN THE SKETCH, then subtract it once —
    # so the cavity is circle INTERSECT halfplane, not circle UNION rectangle.
    h = bore_d * 2
    with BuildSketch(Plane.XY) as dbore:
        Circle(bore_d / 2)
        with Locations((0, flat_cut(bore_d, bore_f, h))):
            Rectangle(h, h, mode=Mode.SUBTRACT)
    extrude(amount=BORE_DEPTH, mode=Mode.SUBTRACT)

    # lead-in on the bore mouth, as a cone rather than a chamfer — same result,
    # but it does not care that the mouth is a D. Lets the coupler self-align
    # onto the shaft instead of you fighting it on with the motor bolted down.
    with Locations((0, 0, 0)):
        Cone(bore_d / 2 + CHAMFER, bore_d / 2, CHAMFER,
             align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

    # Grub screw. It must come in from +Y — that is the side the shaft's flat
    # faces. Driven from -Y it would press on the round side of the shaft and
    # cam the coupler off-centre instead of clamping it.
    with BuildSketch(Plane.XZ.offset(-BODY_D / 2)):
        with Locations((0, BORE_DEPTH * 0.55)):
            Circle(GRUB_PILOT / 2)
    extrude(amount=GRUB_DEPTH, mode=Mode.SUBTRACT)

part = coupler.part
part.label = "fetch_shaft_coupler_5mm_to_7mm"


def gen_step():
    return part


if __name__ == "__main__":
    bb = part.bounding_box()
    print(f"bbox   {bb.size.X:.2f} x {bb.size.Y:.2f} x {bb.size.Z:.2f} mm")
    print(f"volume {part.volume/1000:.2f} cm^3")
    print(f"solids {len(part.solids())}   valid {part.is_valid}")

    # --- the checks that would actually cost you a reprint ---
    assert len(part.solids()) == 1, "must be ONE solid or the slicer guesses"
    assert part.is_valid, "not a valid B-rep"
    assert abs(bb.size.Z - (BODY_LEN + BOSS_LEN)) < 1e-6, "length drifted"
    assert abs(bb.size.X - BODY_D) < 1e-6, "body is not the widest thing"

    # bore floor: shaft must bottom out on plastic, not punch through
    assert BODY_LEN - BORE_DEPTH >= 1.5, "floor under the shaft is too thin"

    # collar wall around the bore — this is what the grub screw pulls against
    wall = (BODY_D - bore_d) / 2
    assert wall >= 3.0, f"collar wall {wall:.2f}mm too thin"

    # the flats must actually bite. If the flat depth rounds to nothing, the
    # bore is effectively round and the coupler WILL spin on the shaft.
    assert bore_d - bore_f >= 0.4, "bore D-flat too shallow to drive"
    assert boss_d - BOSS_FLAT_D >= 0.4, "boss flat too shallow to drive"

    # --- shape probes -------------------------------------------------------
    # The first version of this file cut the flats as circle UNION rectangle
    # instead of circle INTERSECT halfplane. Every dimension check above still
    # passed while the boss was a fin and the bore was a rectangular slot.
    # Dimensions cannot see that. Probing actual points can.
    import math

    def is_solid(x, y, z, r=0.35):
        return (part & Sphere(r).locate(Location((x, y, z)))).volume > 1e-9

    # boss must be a shaft, not a fin
    zb = BODY_LEN + BOSS_LEN / 2
    assert is_solid(0, 0, zb), "boss centre is hollow — the flat cut ate it"
    assert is_solid(0, -boss_d / 2 + 0.6, zb), "boss round side missing"
    assert not is_solid(0, boss_d / 2 + 0.5, zb), "boss flat was never cut"

    # bore must be a D: material on the flat side, cavity on the round side
    assert is_solid(0, BORE_FLAT_Y + 0.45, 5.0), "flat side of bore is void"
    assert not is_solid(0, -2.0, 5.0), "round side of bore is solid"

    # The grub screw must enter on the side the shaft's flat FACES. Driven from
    # -Y it presses the round side and cams the coupler off-centre.
    zg = BORE_DEPTH * 0.55
    assert not is_solid(0, BODY_D / 2 - 1.5, zg), "grub screw is on the wrong side"
    assert is_solid(0, -BODY_D / 2 + 1.5, zg), "grub screw drilled straight through"

    # analytic volume. A circular segment of radius r cut at height c:
    def seg(r, c):
        return r * r * math.acos(c / r) - c * math.sqrt(r * r - c * c)

    a_boss = math.pi * (boss_d / 2) ** 2 - seg(boss_d / 2, -boss_d / 2 + BOSS_FLAT_D)
    a_bore = math.pi * (bore_d / 2) ** 2 - seg(bore_d / 2, -bore_d / 2 + bore_f)
    v_want = (math.pi * (BODY_D / 2) ** 2 * BODY_LEN     # collar
              + a_boss * BOSS_LEN                        # D boss
              - a_bore * BORE_DEPTH                      # D bore
              - math.pi * (GRUB_PILOT / 2) ** 2 * GRUB_DEPTH)
    err = abs(part.volume - v_want) / v_want
    print(f"volume {part.volume:.0f} vs analytic {v_want:.0f} mm^3  ({err*100:.1f}% "
          f"— chamfers + lead-in cone account for the rest)")
    assert err < 0.02, (
        f"volume off by {err*100:.1f}% — a flat was cut as a union, not an "
        f"intersection (that bug read as -27%)")

    # grub screw must break into the bore, and miss the floor
    assert BODY_D / 2 > bore_f - bore_d / 2, "grub screw misses the bore"
    assert BORE_DEPTH * 0.55 + GRUB_PILOT / 2 < BORE_DEPTH, "grub past bore end"

    # torsion. 17HS4401 holds 0.43 Nm; the 7mm boss is the thinnest section.
    T, d = 0.43, boss_d / 1000
    tau = 16 * T / (3.14159 * d**3) / 1e6          # MPa
    assert tau < 8.0, f"boss torsional stress {tau:.1f} MPa too high"
    print(f"\nboss torsion {tau:.1f} MPa vs ~25 MPa PLA layer shear "
          f"-> {25/tau:.1f}x margin (printed standing up)")
    print("all assertions passed")
