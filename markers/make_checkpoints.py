#!/usr/bin/env python3
"""
FETCH — CHECKPOINT POSTERS. One poster, two codes, two readers.

The architecture you described:
    person presses "come to me"
      -> phone maps to a CODE
      -> robot self-drives to that code, avoiding obstacles
      -> robot knows where every code is

The refinement that makes it easy:
    The PHONE does not need to compute its position. It only needs to READ
    WHICH CODE IT CAN SEE. "I see code 7" => "person is at zone 7."
    That is barcode reading (~30 lines, iOS Vision does it natively), NOT
    localization (which is the expensive, blocked thing).

So each poster carries TWO codes, for two different readers:

    APRILTAG (big, top)   -> the ROBOT reads it.
                             Gives full 6DOF pose. Robot learns where IT is,
                             to ~3.7cm when 5+ are visible. This is what
                             replaces SLAM/odometry/TF/Nav2.

    QR CODE  (small, bottom) -> the PHONE reads it.
                             Just the zone id. iOS VNDetectBarcodesRequest,
                             built in, no ARKit, no calibration, no pose math.
                             Person glances at it, taps the button, done.

Same poster. Same wall. Two jobs.
"""
import cv2, numpy as np, os, qrcode

OUT = os.path.dirname(os.path.abspath(__file__))
N = 12
TAG_MM, QR_MM, QUIET_MM = 100, 45, 12
DPI = 300
MM = 25.4
def mm2px(v): return int(round(v / MM * DPI))
A4 = (mm2px(210), mm2px(297))

adict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)

# Human-readable zone names — what the person sees in the app.
ZONES = {
    0: "FOOD COURT",   1: "NORTH ENTRANCE", 2: "ESCALATOR",   3: "BENCH A",
    4: "BENCH B",      5: "WEST WING",      6: "EAST WING",   7: "ATRIUM",
    8: "SOUTH DOORS",  9: "KIOSK",         10: "CORRIDOR 1", 11: "CORRIDOR 2",
}

def qr_img(payload, px):
    q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H,
                      box_size=10, border=2)
    q.add_data(payload); q.make(fit=True)
    im = q.make_image(fill_color="black", back_color="white").convert("L")
    return cv2.resize(np.array(im), (px, px), interpolation=cv2.INTER_NEAREST)

def poster(zid):
    page = np.full((A4[1], A4[0]), 255, np.uint8)
    cx = A4[0] // 2

    # --- AprilTag: for the ROBOT ---
    t = mm2px(TAG_MM)
    tag = cv2.aruco.generateImageMarker(adict, zid, t)
    ty = mm2px(38)
    tx = cx - t//2
    page[ty:ty+t, tx:tx+t] = tag
    cv2.putText(page, "ROBOT READS THIS", (tx, ty-mm2px(6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, 120, 2, cv2.LINE_AA)

    # --- zone name: for the HUMAN ---
    name = ZONES.get(zid, f"ZONE {zid}")
    ny = ty + t + mm2px(22)
    (tw, _), _ = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 2.3, 6)
    cv2.putText(page, name, (cx - tw//2, ny), cv2.FONT_HERSHEY_SIMPLEX, 2.3, 0, 6, cv2.LINE_AA)
    cv2.putText(page, f"FETCH  ZONE {zid}", (cx - tw//2, ny + mm2px(9)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, 110, 2, cv2.LINE_AA)

    # --- QR: for the PHONE ---
    q = mm2px(QR_MM)
    qi = qr_img(f"FETCH:{zid}", q)
    qy = ny + mm2px(20)
    qx = cx - q//2
    page[qy:qy+q, qx:qx+q] = qi
    cv2.putText(page, "POINT YOUR PHONE HERE", (qx-mm2px(14), qy+q+mm2px(9)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, 0, 2, cv2.LINE_AA)
    cv2.putText(page, "then press COME TO ME", (qx-mm2px(11), qy+q+mm2px(17)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, 120, 1, cv2.LINE_AA)
    return page

pages = [poster(i) for i in range(N)]
try:
    from PIL import Image
    ims = [Image.fromarray(p).convert("RGB") for p in pages]
    pdf = os.path.join(OUT, "fetch_CHECKPOINTS_PRINT_ME.pdf")
    ims[0].save(pdf, save_all=True, append_images=ims[1:], resolution=DPI)
    print(f"PDF -> {pdf}  ({N} posters)")
except ImportError:
    pass
cv2.imwrite(os.path.join(OUT, "checkpoint_sample.png"), pages[0])

# ---------------- verify BOTH readers work ----------------
print("\n=== VERIFY: robot reader (AprilTag) ===")
det = cv2.aruco.ArucoDetector(adict, cv2.aruco.DetectorParameters())
ok = 0
for i, p in enumerate(pages):
    small = cv2.resize(p, (0,0), fx=0.12, fy=0.12)   # ~ seeing the poster from afar
    _, ids, _ = det.detectMarkers(small)
    hit = ids is not None and i in ids.flatten()
    ok += hit
print(f"  {ok}/{N} AprilTags detected at 8x downscale")

print("\n=== VERIFY: phone reader (QR) ===")
qd = cv2.QRCodeDetector()
ok2 = 0
for i, p in enumerate(pages):
    small = cv2.resize(p, (0,0), fx=0.30, fy=0.30)
    data, _, _ = qd.detectAndDecode(small)
    hit = data == f"FETCH:{i}"
    ok2 += hit
print(f"  {ok2}/{N} QR codes decoded")

print(f"""
=== HOW THE PIECES FIT ===
   PHONE  reads QR  -> "FETCH:7"       -> POST /come {{"zone": 7}}
   PI     routes through the checkpoint adjacency graph
   ROBOT  reads the next AprilTag and visually steers toward it
   UNO    five ultrasonic sensors veto unsafe motion in hard real-time

   The phone NEVER computes its position. It reads a number off a wall.
   That is the whole trick.

=== VENUE MAP ===
   Create the graph with tools/make_topo_map.py. No coordinates or survey.

=== PRINTING ===
   100% / Actual Size. Then RULER the AprilTag: must be exactly {TAG_MM}mm.
   Matte, glued to card. Each next checkpoint must be visible from the prior one.
""")
