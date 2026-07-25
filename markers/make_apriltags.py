#!/usr/bin/env python3
"""
Generate printable tag36h11 AprilTags 0-4, then PROVE they work by running
the very detector the robot uses (pupil_apriltags) over the rendered pages.

Why generate rather than download: the family must match the detector exactly.
fetch_auto.py uses families="tag36h11", and cv2.aruco's DICT_APRILTAG_36h11 is
that same family, so a round-trip test here is a real guarantee, not a guess.

Output: one PNG per tag plus a 5-page PDF, ready to print at 100% scale.
"""
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

DPI = 300
TAG_MM = 140                 # printed black-square size; big = seen from far
PAGE_W_MM, PAGE_H_MM = 216, 279          # US Letter
IDS = [0, 1, 2, 3, 4]
OUT = "/Users/rishith/Desktop/FETCH_apriltags"

mm = lambda v: int(round(v / 25.4 * DPI))


def render_tag(tag_id, px):
    """tag36h11 bitmap at px x px, nearest-neighbour so cells stay crisp."""
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    small = cv2.aruco.generateImageMarker(d, tag_id, 200)
    return cv2.resize(small, (px, px), interpolation=cv2.INTER_NEAREST)


def make_page(tag_id):
    page = Image.new("L", (mm(PAGE_W_MM), mm(PAGE_H_MM)), 255)
    tag_px = mm(TAG_MM)
    tag = Image.fromarray(render_tag(tag_id, tag_px))

    x = (page.width - tag_px) // 2
    y = mm(45)
    page.paste(tag, (x, y))

    dr = ImageDraw.Draw(page)
    try:
        big = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf", mm(11))
        small = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial.ttf", mm(4.5))
    except Exception:
        big = small = ImageFont.load_default()

    dr.text((x, mm(22)), f"TAG {tag_id}", font=big, fill=0)
    dr.text((x, y + tag_px + mm(10)),
            f"tag36h11  ·  id {tag_id}  ·  {TAG_MM} mm  ·  print at 100% (no fit-to-page)",
            font=small, fill=90)
    dr.text((x, y + tag_px + mm(18)),
            "Keep the white margin around the tag clear - the detector needs it.",
            font=small, fill=90)

    # corner crop marks, well outside the tag's quiet zone
    q = mm(8)
    for cx, cy in [(x - q, y - q), (x + tag_px + q, y - q),
                   (x - q, y + tag_px + q), (x + tag_px + q, y + tag_px + q)]:
        dr.line([(cx - mm(4), cy), (cx + mm(4), cy)], fill=160, width=3)
        dr.line([(cx, cy - mm(4)), (cx, cy + mm(4))], fill=160, width=3)
    return page


def verify(pages):
    """Detect with the robot's own detector. This is the actual guarantee."""
    from pupil_apriltags import Detector
    det = Detector(families="tag36h11", nthreads=2)
    ok = True
    for tag_id, page in zip(IDS, pages):
        arr = np.array(page)
        # shrink to roughly what the webcam sees, so the test is realistic
        h = 480
        w = int(arr.shape[1] * h / arr.shape[0])
        shrunk = cv2.resize(arr, (w, h), interpolation=cv2.INTER_AREA)
        found = det.detect(shrunk)
        ids = [d.tag_id for d in found]
        good = ids == [tag_id]
        ok &= good
        print(f"  tag {tag_id}: detected {ids}  "
              f"{'OK' if good else '*** MISMATCH ***'}")
    return ok


if __name__ == "__main__":
    import os
    os.makedirs(OUT, exist_ok=True)
    pages = [make_page(i) for i in IDS]
    for i, p in zip(IDS, pages):
        p.save(f"{OUT}/apriltag_{i}.png", dpi=(DPI, DPI))
    pages[0].save(f"{OUT}/apriltags_0-4.pdf", "PDF", resolution=DPI,
                  save_all=True, append_images=pages[1:])
    print(f"wrote {len(pages)} PNGs + apriltags_0-4.pdf to {OUT}")
    print("verifying with the robot's own detector, at webcam resolution:")
    sys.exit(0 if verify(pages) else 1)
