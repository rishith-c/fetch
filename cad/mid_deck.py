"""
MID DECK — electronics plate riding 8mm above the aluminum chassis plate on
integrated feet. Carries the Pi 4B and the Freenove Uno R4 on proper hole
patterns; everything else (L298N x2, bucks) lives on the aluminum below on
foam tape, or zip-ties into the slot field. Battery straps through two slots.

Plate 170 x 130 x 3, corner feet 10x10x8 with M3 clearance to bolt through
the chassis slots. Prints upside-down (top face on bed, feet up) - no supports.
"""
from build123d import *

W, L, T = 170.0, 130.0, 3.0
FOOT, FOOT_H = 12.0, 8.0
M3 = 3.4
FEET = [(78, 58), (-78, 58), (-78, -58), (78, -58)]

# Pi 4B: 58 x 49 pattern, M2.5 -> 2.8 clearance; board 85x56, center-left
PI_C = (-38, 25)
PI_HOLES = [(PI_C[0]+dx, PI_C[1]+dy) for dx in (-29, 29) for dy in (-24.5, 24.5)]
# Uno R4 pattern (68.6x53.4 board ref, recentred), placed center-right
_raw = [(15.24, 50.80), (66.04, 35.56), (66.04, 7.62), (13.97, 2.54)]
UNO_C = (42, 22)
UNO_HOLES = [(UNO_C[0]+x-68.6/2, UNO_C[1]+y-53.4/2) for (x, y) in _raw]
# battery strap slots (22x4) near the rear edge
STRAPS = [(-30, -45), (30, -45)]
# zip-tie slot field rows (4x8 slots) across the free zone
ZIPS = [(x, y) for y in (-15, -32) for x in (-60, -30, 0, 30, 60)]

with BuildPart() as deck:
    Box(W, L, T, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # feet
    with BuildSketch(Plane.XY.offset(T)):
        with Locations(*FEET):
            Rectangle(FOOT, FOOT)
    extrude(amount=FOOT_H)
    # foot bolt holes through everything
    with BuildSketch():
        with Locations(*FEET):
            Circle(M3 / 2)
    extrude(amount=T + FOOT_H, mode=Mode.SUBTRACT)
    # Pi holes (2.8) + Uno holes (3.2)
    with BuildSketch():
        with Locations(*PI_HOLES):
            Circle(2.8 / 2)
        with Locations(*UNO_HOLES):
            Circle(3.2 / 2)
    extrude(amount=T, mode=Mode.SUBTRACT)
    # strap + zip slots
    with BuildSketch():
        with Locations(*STRAPS):
            SlotOverall(22, 4)
        with Locations(*ZIPS):
            SlotOverall(8, 3)
    extrude(amount=T, mode=Mode.SUBTRACT)
    # big wire pass-through ovals, clear of hole patterns
    with BuildSketch():
        with Locations((0, 45), (0, -2)):
            SlotOverall(40, 12)
    extrude(amount=T, mode=Mode.SUBTRACT)

part = deck.part
part.label = "mid_deck"


def gen_step():
    return part


if __name__ == "__main__":
    bb = part.bounding_box()
    assert len(part.solids()) == 1 and part.is_valid
    assert abs(bb.size.Z - (T + FOOT_H)) < 1e-6
    # every hole pattern stays on the plate
    for hx, hy in PI_HOLES + UNO_HOLES + FEET:
        assert abs(hx) < W/2 - 2 and abs(hy) < L/2 - 2, (hx, hy)
    print(f"deck OK  {bb.size.X:.0f}x{bb.size.Y:.0f}x{bb.size.Z:.0f}")
