"""
FETCH v2 HD — high-detail full-vehicle mockup.

Layout changes vs v1 mockup (per build decision):
  - 5x HC-SR04 in a BELT around the can at mid-height (z~270) on the friend's ring
  - MG90S servo + webcam near the can TOP (z~400), tilt axis horizontal
  - wire looms modeled: deck->belt loom and deck->top servo/cam loom
Detail level: mecanum rollers (8/wheel, mirrored L/R), slotted chassis plate,
L298N w/ heatsink+terminals, XL4015 w/ coil+pot, Pi w/ ports+GPIO, Uno w/
headers+USB, sonar eyes, fuse holder inline off the battery.
"""
from build123d import *
from build123d import Color
import math

parts = []
def add(shape, label, color):
    shape.label = label; shape.color = Color(color); parts.append(shape)

PLATE_TOP, PLATE_T = 89.0, 3.0
AXLE_Z = 33.0
LEG_TOP = PLATE_TOP + 45
CAN_Z = LEG_TOP + 4.0            # 138 can base
BELT_Z = 270.0                   # sonar belt height
CAN_R = lambda z: 90 + 20*(z-CAN_Z)/270.0

# ---------- chassis plate with slot field ----------
plate = Box(140, 180, PLATE_T)
slots = []
for yy in (-70, -50, -30, 30, 50, 70):
    for xx in (-40, 0, 40):
        slots.append(Location((xx, yy, 0)) * SlotOverall(30, 4).face())
for s in slots:
    plate -= extrude(s, PLATE_T*2, both=True)
add(plate.locate(Location((0, 0, PLATE_TOP - PLATE_T/2))), "chassis_plate", "#b8bcc2")

# ---------- mecanum wheels with rollers ----------
for sx in (-1, 1):
    for sy in (-1, 1):
        cx, cy = sx*87, sy*67.5
        drum = Cylinder(21, 26, rotation=(0, 90, 0)).locate(Location((cx, cy, AXLE_Z)))
        add(drum, f"drum_{sx}{sy}", "#2a2a2e")
        for side in (-13, 13):
            disc = Cylinder(27, 3, rotation=(0, 90, 0)).locate(Location((cx+side*0.9, cy, AXLE_Z)))
            add(disc, f"disc_{sx}{sy}{side}", "#3a3a40")
        hub = Cylinder(9, 30, rotation=(0, 90, 0)).locate(Location((cx, cy, AXLE_Z)))
        add(hub, f"hub_{sx}{sy}", "#d4a017")
        mirror = sx*sy   # X-pattern: diagonal pairs share roller handedness
        for k in range(8):
            th = k*45.0
            base = Cylinder(4.2, 19, rotation=(90, 0, 0))          # axis along Y
            loc = (Location((cx, cy, AXLE_Z)) * Rotation(th, 0, 0)
                   * Location((0, 0, 28.5)) * Rotation(0, 0, 45*mirror))
            add(base.locate(loc), f"roller_{sx}{sy}_{k}", "#151518")
        motor = Box(37, 20, 20).locate(Location((sx*48, cy, AXLE_Z)))
        add(motor, f"ttmotor_{sx}{sy}", "#e8c619")
        gearbox = Box(23, 22.5, 19).locate(Location((sx*20, cy, AXLE_Z)))
        add(gearbox, f"gearbox_{sx}{sy}", "#f5f0e6")

# ---------- electronics on plate ----------
for i, px in enumerate((-38, 38)):
    pcb = Box(43, 43, 1.8).locate(Location((px, -55, PLATE_TOP+1)))
    add(pcb, f"L298N_pcb_{i}", "#b3202a")
    hs = Box(16, 23, 24).locate(Location((px, -55, PLATE_TOP+14)))
    for f_i, fy in enumerate((-9, 0, 9)):
        fin = Box(20, 2.5, 24).locate(Location((px, -55+fy, PLATE_TOP+14)))
        add(fin, f"L298N_fin_{i}_{f_i}", "#111")
    add(hs, f"L298N_hs_{i}", "#161616")
    for tb_i, tx in enumerate((-15, 15)):
        tb = Box(10, 8, 10).locate(Location((px+tx, -72, PLATE_TOP+5)))
        add(tb, f"L298N_term_{i}_{tb_i}", "#1450b4")
for i, bx in enumerate((-48, 0, 48)):
    pcb = Box(51, 23, 1.8).locate(Location((bx, -12, PLATE_TOP+1)))
    add(pcb, f"XL4015_pcb_{i}", "#0f6e3c")
    coil = (Cylinder(8, 9).locate(Location((bx-10, -12, PLATE_TOP+6))))
    add(coil, f"XL4015_coil_{i}", "#c87f42")
    pot = Box(9, 9, 6).locate(Location((bx+15, -12, PLATE_TOP+5)))
    add(pot, f"XL4015_pot_{i}", "#3a6cc8")
add(Box(112, 20, 18).locate(Location((0, 22, PLATE_TOP+9))), "battery_11v1", "#e07820")
add(Cylinder(5.5, 30, rotation=(0, 90, 0)).locate(Location((-70, 22, PLATE_TOP+8))),
    "fuse_holder_7A5", "#101010")
add(Box(22, 8, 8).locate(Location((-56, 40, PLATE_TOP+4))), "switch", "#c02020")

# ---------- mid-deck + Pi + Uno ----------
DECK_Z = PLATE_TOP + 34
add(Box(170, 130, 3).locate(Location((0, 25, DECK_Z))), "mid_deck", "#4a4a50")
piz = DECK_Z + 2.5
add(Box(85, 56, 1.8).locate(Location((-38, 45, piz))), "pi4_pcb", "#1e7a34")
add(Box(15, 13, 15).locate(Location((-4, 32, piz+8))), "pi_usb1", "#c8c8cc")
add(Box(15, 13, 15).locate(Location((-4, 50, piz+8))), "pi_usb2", "#c8c8cc")
add(Box(16, 14, 12).locate(Location((-4, 66, piz+7))), "pi_eth", "#b0b4bc")
add(Box(50, 5, 8).locate(Location((-50, 68, piz+5))), "pi_gpio", "#111")
add(Box(15, 15, 2.5).locate(Location((-55, 45, piz+2))), "pi_soc", "#666")
add(Box(69, 53, 1.8).locate(Location((42, 42, piz))), "unoR4_pcb", "#0e6e6e")
add(Box(45, 5, 9).locate(Location((40, 63, piz+5))), "uno_hdrN", "#111")
add(Box(45, 5, 9).locate(Location((40, 21, piz+5))), "uno_hdrS", "#111")
add(Box(9, 9, 4).locate(Location((70, 30, piz+3))), "uno_usbc", "#c8c8cc")
add(Box(14, 12, 3).locate(Location((20, 42, piz+3))), "uno_esp32", "#888")

# ---------- legs + crown ----------
for lx, ly in [(70,55), (-70,55), (-70,-55), (70,-55)]:
    add(Cylinder(7, 45).locate(Location((lx, ly, PLATE_TOP+22.5))), f"leg_{lx}_{ly}", "#e8860a")
crown = Cylinder(95, 4).locate(Location((0,0,LEG_TOP+2))) - Cylinder(75, 6).locate(Location((0,0,LEG_TOP+2)))
lip = Cylinder(95, 12).locate(Location((0,0,LEG_TOP+10))) - Cylinder(91, 14).locate(Location((0,0,LEG_TOP+10)))
add(crown+lip, "can_crown", "#e8860a")

# ---------- can ----------
can = Cone(90, 110, 270, align=(Align.CENTER,Align.CENTER,Align.MIN)).locate(Location((0,0,CAN_Z)))
add(can, "trashcan", "#70747a")

# ---------- sonar belt at mid-can (friend's printed ring) ----------
rb = CAN_R(BELT_Z)
band = Cylinder(rb+4, 26).locate(Location((0,0,BELT_Z))) - Cylinder(rb+0.5, 28).locate(Location((0,0,BELT_Z)))
add(band, "sonar_ring_printed", "#d4a017")
for i, ang in enumerate([90, 45, 135, -45, -135]):     # front, FR, FL, RR, RL (deg, +Y=front)
    a = math.radians(ang)
    px, py = (rb+6)*math.cos(a), (rb+6)*math.sin(a)
    rz = ang - 90
    pcb = Box(45, 6, 20, rotation=(0,0,rz)).locate(Location((px, py, BELT_Z)))
    add(pcb, f"HCSR04_{i}_pcb", "#1450b4")
    tx, ty = math.cos(a), math.sin(a)
    nx, ny = -math.sin(a), math.cos(a)
    for eye_s in (-12, 12):
        ex, ey = px+nx*eye_s+tx*5, py+ny*eye_s+ty*5
        eye = Cylinder(8, 12, rotation=(90,0,rz)).locate(Location((ex, ey, BELT_Z)))
        add(eye, f"HCSR04_{i}_eye{eye_s}", "#c8ccd4")

# ---------- servo + webcam near can top ----------
TOP_Z = 395.0
rt = CAN_R(TOP_Z)
mount = Box(30, 12, 40).locate(Location((0, rt+6, TOP_Z-10)))
add(mount, "cam_bracket_printed", "#d4a017")
servo = Box(23, 12.5, 23).locate(Location((0, rt+13, TOP_Z+8)))
add(servo, "MG90S_servo", "#20242a")
horn = Cylinder(4, 26, rotation=(0,90,0)).locate(Location((0, rt+13, TOP_Z+21)))
add(horn, "servo_shaft", "#e8e8e8")
cam = Box(32, 28, 26).locate(Location((0, rt+22, TOP_Z+21)))
add(cam, "webcam", "#0c0c0e")
lens = Cylinder(9, 6, rotation=(90,0,0)).locate(Location((0, rt+37, TOP_Z+21)))
add(lens, "lens", "#1a2c4a")

# ---------- wire looms (deck -> belt, deck -> top) ----------
for i, (zz0, zz1, lbl) in enumerate([(DECK_Z, BELT_Z-13, "loom_sonars_8wire"),
                                      (DECK_Z, TOP_Z, "loom_servo_3wire")]):
    seg = zz1 - zz0
    loom = Cylinder(2.5, seg, align=(Align.CENTER,Align.CENTER,Align.MIN)).locate(
        Location((28+i*10, 88+i*4, zz0)))
    add(loom, lbl, "#c02020" if i==0 else "#222")

asm = Compound(children=parts)
asm.label = "fetch_v2_hd"
part = asm

def gen_step():
    return part

if __name__ == "__main__":
    bb = part.bounding_box()
    print(f"envelope {bb.size.X:.0f} x {bb.size.Y:.0f} x {bb.size.Z:.0f}  solids={len(part.solids())}")
    assert len(parts) > 80
    print("HD assembly OK")
