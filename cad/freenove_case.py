"""
Simple 3D-printable BOTTOM CRADLE for the Freenove Control Board V5 (Uno R4
form factor, 69 x 54 mm). Open top so the CNC shield still plugs in; walls +
floor protect the underside and edges; the left wall is cut for the USB-C and
DC jack.

TOLERANCE: the board pocket is board + 0.5 mm per side, so it drops in on an
FDM print without forcing.

SCREW HOLES: standoffs sit at the standard Arduino Uno mounting-hole pattern
with M3 self-tap pilots. Freenove uses the Uno pattern, but if a boss is a hair
off, the board still rests on the boss tops — retention doesn't depend on the
screws lining up.

Print flat on the floor, no supports. ~2-3 h.
"""
from build123d import *

# ---- board ----
BW, BL, BT = 69.0, 54.0, 1.6

# ---- case ----
CLR      = 0.5     # per-side clearance around the board (FDM drop-in fit)
WALL     = 2.5
FLOOR    = 2.5
STANDOFF = 4.0     # board floats this high above the floor (clears solder tails)
WALL_H   = 10.0    # wall height above the floor (below header tops so the shield seats)
BOSS_D   = 6.0
PILOT    = 2.6     # M3 self-tapping pilot

cav_w, cav_l = BW + 2*CLR, BL + 2*CLR
out_w, out_l = cav_w + 2*WALL, cav_l + 2*WALL

# Arduino Uno standard mounting holes (68.6 x 53.4 ref), recentred to the origin
_raw = [(15.24, 50.80), (66.04, 35.56), (66.04, 7.62), (13.97, 2.54)]
HOLES = [(x - 68.6/2, y - 53.4/2) for (x, y) in _raw]

with BuildPart() as case:
    # floor
    Box(out_w, out_l, FLOOR, align=(Align.CENTER, Align.CENTER, Align.MIN))

    # perimeter walls
    with BuildSketch(Plane.XY.offset(FLOOR)):
        Rectangle(out_w, out_l)
        Rectangle(cav_w, cav_l, mode=Mode.SUBTRACT)
    extrude(amount=WALL_H)

    # screw-boss standoffs (also carry the board)
    with BuildSketch(Plane.XY.offset(FLOOR)):
        with Locations(*HOLES):
            Circle(BOSS_D / 2)
    extrude(amount=STANDOFF)
    with BuildSketch(Plane.XY.offset(FLOOR)):
        with Locations(*HOLES):
            Circle(PILOT / 2)
    extrude(amount=STANDOFF, mode=Mode.SUBTRACT)

    # port openings in the LEFT (-X) wall: USB-C (upper), DC jack (lower).
    # cut full wall height so both connectors clear regardless of exact height.
    for yc, wd in [(19.0, 16.0), (-18.0, 16.0)]:
        with Locations((-cav_w/2 - WALL/2, yc, FLOOR + WALL_H/2)):
            Box(WALL + 4, wd, WALL_H + 0.1, mode=Mode.SUBTRACT)

    # a couple of vent/cable slots in the floor
    with BuildSketch(Plane.XY):
        with Locations((0, 12), (0, -12)):
            SlotOverall(34, 5, rotation=0)
    extrude(amount=FLOOR, mode=Mode.SUBTRACT)

part = case.part
part.label = "freenove_case"


def gen_step():
    return part


if __name__ == "__main__":
    bb = part.bounding_box()
    print(f"outer  {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")
    print(f"pocket {cav_w:.1f} x {cav_l:.1f} mm  (board {BW}x{BL} + {CLR}/side)")
    print(f"solids {len(part.solids())}   valid {part.is_valid}")

    def solid(x, y, z, r=0.4):
        return (part & Sphere(r).locate(Location((x, y, z)))).volume > 1e-9

    assert len(part.solids()) == 1, "must be one solid"
    assert part.is_valid, "invalid B-rep"
    assert abs(bb.size.Z - (FLOOR + WALL_H)) < 1e-6, "height off"
    # board actually fits the pocket with clearance
    assert cav_w >= BW and cav_l >= BL, "pocket too small for board"
    # bosses exist and are inside the pocket
    for hx, hy in HOLES:
        assert abs(hx) < cav_w/2 and abs(hy) < cav_l/2, "a boss is outside the pocket"
        assert solid(hx + 2, hy, FLOOR + STANDOFF - 0.5), "boss missing"
    # floor present, port wall opened
    assert solid(cav_w/2, 0, FLOOR/2), "floor missing"
    assert not solid(-cav_w/2 - WALL/2, 19, FLOOR + WALL_H/2), "USB-C opening not cut"
    assert not solid(-cav_w/2 - WALL/2, -18, FLOOR + WALL_H/2), "DC opening not cut"
    print("all assertions passed")
