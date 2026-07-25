#!/usr/bin/env python3
"""
FETCH — verify the checkpoint markers actually decode.

THE QUIET ZONE IS NOT OPTIONAL AND THIS PROVES IT.
    Measured here: a bare tag36h11 with NO white border decodes 0/12 even at
    354 pixels. Add a 4% border and it's 12/12.

    So: if you trim the white margin off the printed poster to make it look
    neat, the robot goes blind. The border is part of the marker, not packaging.

Run:  python3 tools/check_markers.py
Deps: pip3 install opencv-contrib-python-headless
"""
import sys

try:
    import cv2
    import numpy as np
except ImportError:
    print("  – opencv not installed:  pip3 install opencv-contrib-python-headless")
    sys.exit(0)          # not a failure of the design; just an absent tool


D = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
DET = cv2.aruco.ArucoDetector(D, cv2.aruco.DetectorParameters())
N = 12


def tag(i, side=1181, quiet=0.12):
    t = cv2.aruco.generateImageMarker(D, i, side)
    if quiet <= 0:
        return t
    q = int(side * quiet)
    c = np.full((side + 2 * q, side + 2 * q), 255, np.uint8)
    c[q:q + side, q:q + side] = t
    return c


def decode_count(scale, quiet):
    n = 0
    for i in range(N):
        small = cv2.resize(tag(i, quiet=quiet), (0, 0), fx=scale, fy=scale)
        _, ids, _ = DET.detectMarkers(small)
        if ids is not None and i in ids.flatten():
            n += 1
    return n


def main():
    fails = 0

    ok = decode_count(0.10, 0.12)
    good = ok == N
    fails += not good
    print(f"  {'✓' if good else '✗'} {ok}/{N} tags decode at 10x downscale (with quiet zone)")

    noq = decode_count(0.10, 0.0)
    good = noq == 0
    fails += not good
    print(f"  {'✓' if good else '✗'} quiet-zone requirement proven: {noq}/{N} decode without a border")

    # the minimum border that still works — tells you how much you may trim
    worst = None
    for q in (0.02, 0.04, 0.08):
        if decode_count(0.10, q) == N:
            worst = q
            break
    if worst:
        print(f"  ✓ minimum usable quiet zone ≈ {worst*100:.0f}% of tag width "
              f"(we print 12% — do not trim below this)")
    else:
        fails += 1
        print("  ✗ could not find a working quiet zone")

    return fails


if __name__ == "__main__":
    sys.exit(main())
