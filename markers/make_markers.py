#!/usr/bin/env python3
"""
FETCH — generate printable checkpoint markers.

This makes the "paintings" you tape to the walls. They are AprilTag tag36h11,
which is what the research says to use:
  - tag36h11 / ArUco / STag all detect >90%. ARTag manages ~45% — don't use it.
  - Marker COUNT dominates accuracy, not marker size:
        1 marker visible  -> 45.3 cm position error
        3 markers visible ->  8.8 cm
        5 markers visible ->  3.7 cm   <-- design target
  - So: place them so 5+ are visible from ANYWHERE the robot drives.
  - Mount them ANGLED, not flat-on. Head-on views suffer pose ambiguity.

Output: one PDF per page, 2 markers per A4 sheet at 100mm, with the ID printed
below each and a cut line. 100mm reads reliably at ~5m on a 1080p camera.
"""
import cv2
import numpy as np
import os

OUT = os.path.dirname(os.path.abspath(__file__))

# --- config ---
DICT = cv2.aruco.DICT_APRILTAG_36h11
N_MARKERS = 12                 # ids 0..11 — plenty for a demo area
MARKER_MM = 100                # printed size of the black square
QUIET_MM = 12                  # white border. NOT optional — detection needs it.
DPI = 300

MM_PER_IN = 25.4
def mm2px(mm): return int(round(mm / MM_PER_IN * DPI))

A4_W_MM, A4_H_MM = 210, 297
page_w, page_h = mm2px(A4_W_MM), mm2px(A4_H_MM)

adict = cv2.aruco.getPredefinedDictionary(DICT)

def render_marker(mid):
    """Marker bitmap at print resolution, with quiet zone."""
    side = mm2px(MARKER_MM)
    img = cv2.aruco.generateImageMarker(adict, mid, side)
    q = mm2px(QUIET_MM)
    canvas = np.full((side + 2*q, side + 2*q), 255, dtype=np.uint8)
    canvas[q:q+side, q:q+side] = img
    return canvas

def make_page(ids):
    page = np.full((page_h, page_w), 255, dtype=np.uint8)
    n = len(ids)
    slot_h = page_h // n
    for i, mid in enumerate(ids):
        m = render_marker(mid)
        mh, mw = m.shape
        y0 = i * slot_h + (slot_h - mh) // 2 - mm2px(6)
        x0 = (page_w - mw) // 2
        y0 = max(y0, mm2px(4))
        page[y0:y0+mh, x0:x0+mw] = m
        # label under the marker
        label = f"FETCH  id={mid}   {MARKER_MM}mm  tag36h11"
        cv2.putText(page, label, (x0, min(y0+mh+mm2px(9), page_h-10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, 0, 2, cv2.LINE_AA)
        # cut guide between slots
        if i < n-1:
            yc = (i+1) * slot_h
            for x in range(mm2px(8), page_w-mm2px(8), 26):
                cv2.line(page, (x, yc), (x+13, yc), 170, 1)
    return page

pages = []
ids = list(range(N_MARKERS))
for i in range(0, len(ids), 2):
    pages.append(make_page(ids[i:i+2]))

# save PNGs
png_paths = []
for i, p in enumerate(pages):
    fp = os.path.join(OUT, f"fetch_markers_page{i+1}.png")
    cv2.imwrite(fp, p)
    png_paths.append(fp)

# single combined PDF
try:
    from PIL import Image
    imgs = [Image.fromarray(p).convert("RGB") for p in pages]
    pdf = os.path.join(OUT, "fetch_markers_PRINT_ME.pdf")
    imgs[0].save(pdf, save_all=True, append_images=imgs[1:], resolution=DPI)
    print(f"PDF  -> {pdf}")
except ImportError:
    print("(PIL missing — PNGs only)")

for p in png_paths:
    print(f"PNG  -> {p}")

# --- verification: detect them back ---
print("\n=== VERIFY: detect the markers we just made ===")
det = cv2.aruco.ArucoDetector(adict, cv2.aruco.DetectorParameters())
ok = 0
for mid in ids:
    img = render_marker(mid)
    small = cv2.resize(img, (0, 0), fx=0.14, fy=0.14)  # simulate seeing it at distance
    corners, found, _ = det.detectMarkers(small)
    hit = found is not None and mid in found.flatten()
    ok += hit
    print(f"  id {mid:>2}: {'detected' if hit else 'FAILED'}")
print(f"\n{ok}/{len(ids)} detected after 7x downscale (simulates ~5m viewing)")

print(f"""
=== PRINT + PLACE INSTRUCTIONS ===
1. Print fetch_markers_PRINT_ME.pdf at **100% / Actual Size**.
   NOT "fit to page" — that rescales and every distance measurement breaks.
2. Measure a printed black square with a ruler. It MUST be {MARKER_MM}mm.
   If it isn't, your printer scaled it. Fix that before anything else.
3. Mount on something RIGID and FLAT. A floppy paper curls and ruins pose.
   Glue to cardboard/foamboard.
4. MATTE only. Glossy paper or lamination = glare = no detection.
5. Keep the white border. It is part of the marker, not packaging.
6. Place so **5+ markers are visible from anywhere the robot drives.**
   This is the single biggest accuracy lever (45cm -> 3.7cm).
7. **ANGLE them** (~90 deg apart around the room), don't line them all up
   facing the same way. Head-on views are ambiguous.
8. Measure each marker's real-world (x, y, height, facing) into markers.json.
   THIS SURVEY IS THE HIDDEN COST. Budget an hour. Use a tape measure and
   be honest — every error here becomes robot error forever.
""")
