"""
FETCH v2 — full-vehicle mockup assembly (visual, real envelope dimensions).

Ground = Z0. Kit: plate 180x140 with top at 89mm, wheels D66xW30 at corners
(201mm outer length per drawing -> wheel centers at x=+-85.5... use drawing:
201 total incl wheels, wheelbase along 180 side). Stack: L298N x2 + bucks on
plate -> mid-deck (Pi + Uno) -> 4 legs -> crown -> tapered can 180->220 x270.
Sonars around plate rim, webcam + tilt servo on a front mast.
"""
from build123d import *
from build123d import Color

parts = []

def add(shape, label, color):
    shape.label = label
    shape.color = Color(color)
    parts.append(shape)

PLATE_TOP = 89.0
PLATE_T = 3.0
WHEEL_D, WHEEL_W = 66.0, 30.0
WHEEL_CX, WHEEL_CY = 67.5, 85.0     # centers: 201-66=135/2=67.5 (length axis=Y per drawing 140 wide x 180 long)
# drawing: plate 140 wide (X) x 180 long (Y); wheels outside the 140 width
AXLE_Z = WHEEL_D / 2

# ---- chassis plate ----
add(Box(140, 180, PLATE_T).locate(Location((0, 0, PLATE_TOP - PLATE_T/2))),
    "chassis_plate", "silver")

# ---- wheels + rollers + motors ----
for sx in (-1, 1):
    for sy in (-1, 1):
        cx = sx * (140/2 + WHEEL_W/2 + 2)
        cy = sy * WHEEL_CY * 0.79   # ~67 -> matches 201 envelope
        wheel = Cylinder(WHEEL_D/2, WHEEL_W, rotation=(0, 90, 0)).locate(
            Location((cx, cy, AXLE_Z)))
        add(wheel, f"mecanum_{'F' if sy>0 else 'R'}{'R' if sx>0 else 'L'}", "gray20")
        hub = Cylinder(20, WHEEL_W+2, rotation=(0, 90, 0)).locate(Location((cx, cy, AXLE_Z)))
        add(hub, f"hub_{sx}_{sy}", "gold")
        motor = Box(65, 22, 22, rotation=(0, 0, 0)).locate(
            Location((sx*30, cy, AXLE_Z + 8)))
        add(motor, f"tt_motor_{sx}_{sy}", "yellow")

# ---- electronics on plate: 2x L298N + 3x XL4015 + battery ----
for i, sx in enumerate((-1, 1)):
    add(Box(43, 43, 27).locate(Location((sx*38, -55, PLATE_TOP + 13.5))),
        f"L298N_{i+1}", "firebrick")
for i, x in enumerate((-45, 0, 45)):
    add(Box(51, 23, 14).locate(Location((x, -12, PLATE_TOP + 7))),
        f"XL4015_{i+1}", "royalblue")
add(Box(112, 20, 18).locate(Location((0, 20, PLATE_TOP + 9))),
    "battery_11v1", "darkorange")

# ---- mid-deck + Pi + Uno ----
DECK_Z = PLATE_TOP + 34
add(Box(170, 130, 3).locate(Location((0, 25, DECK_Z))), "mid_deck", "dimgray")
add(Box(85, 56, 18).locate(Location((-38, 45, DECK_Z + 10.5))), "raspberry_pi4", "green")
add(Box(69, 53, 16).locate(Location((42, 42, DECK_Z + 9.5))), "uno_r4_wifi", "teal")

# ---- crown legs + crown ring ----
LEG_H, LEG_TOP = 45.0, PLATE_TOP + 45
for sx in (-1, 1):
    for sy in (-1, 1):
        add(Cylinder(7, LEG_H).locate(Location((sx*70, sy*55, PLATE_TOP + LEG_H/2))),
            f"leg_{sx}_{sy}", "orange")
crown = Cylinder(95, 4).locate(Location((0, 0, LEG_TOP + 2)))
crown -= Cylinder(75, 5).locate(Location((0, 0, LEG_TOP + 2)))
lip = Cylinder(95, 12).locate(Location((0, 0, LEG_TOP + 4 + 6)))
lip -= Cylinder(91, 13).locate(Location((0, 0, LEG_TOP + 4 + 6)))
add(crown + lip, "can_crown", "orange")

# ---- the trashcan: taper 180 base -> 220 top, 270 tall ----
CAN_Z = LEG_TOP + 4
can = Cone(90, 110, 270, align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
    Location((0, 0, CAN_Z)))
can -= Cone(87, 107, 270, align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
    Location((0, 0, CAN_Z + 3)))
add(can, "trashcan_620g", "gray40")

# ---- 5 sonars on plate rim + webcam mast on crown front ----
SON = [(0, 92, 0), (-62, 80, 30), (62, 80, -30), (-62, -92, 150), (62, -92, -150)]
for i, (x, y, rz) in enumerate(SON):
    add(Box(45, 15, 20, rotation=(0, 0, rz)).locate(Location((x, y*0.95, PLATE_TOP + 10))),
        f"HCSR04_{i+1}", "steelblue")
add(Cylinder(4, 60).locate(Location((0, 95, LEG_TOP + 30))), "cam_mast", "gray30")
add(Box(28, 28, 28).locate(Location((0, 100, LEG_TOP + 66))), "webcam_on_servo", "black")

asm = Compound(children=parts)
asm.label = "fetch_v2"
part = asm


def gen_step():
    return part


if __name__ == "__main__":
    bb = part.bounding_box()
    print(f"envelope {bb.size.X:.0f} x {bb.size.Y:.0f} x {bb.size.Z:.0f} mm, "
          f"{len(part.solids())} solids")
    assert bb.size.Z < 480 and len(parts) >= 20
    print("assembly OK")
