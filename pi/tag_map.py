#!/usr/bin/env python3
"""
TAG MAP - what "the robot knows where the art piece is" actually means here.

THE HONEST CONSTRAINT
---------------------
This robot has no encoders, no IMU, no lidar. There is no way to know its
(x, y) in the room, and dead reckoning from step counts is hopeless on mecanum
wheels - they slip sideways by design, so the error grows every second.

So we do not store a room coordinate. We store a VIEW.

WHAT A CALIBRATION IS
---------------------
Park the robot exactly where you want it to end up. Point it at the art
piece's tag. Press Calibrate. We record what the tag LOOKS LIKE from that
spot:

    area    - how many pixels the tag quad covers  -> encodes DISTANCE
              (twice as far = a quarter the area, it is pure inverse-square)
    cx      - how far off-centre it sits, -1..+1   -> encodes BEARING
    tilt    - the servo angle that framed it       -> encodes HEIGHT

Those three numbers ARE the location, expressed relative to the landmark
instead of relative to the room. Driving until the live view matches the
saved view puts the robot back on the same spot - that is visual servoing,
and unlike odometry its error does not accumulate. Every frame is a fresh
absolute fix against something bolted to the wall.

WHY THIS BEATS COORDINATES FOR THIS ROBOT
-----------------------------------------
Push the robot sideways mid-run and an odometry system is lost forever. This
one just sees a different view and corrects. The tag is the ground truth.
"""
import json
import os
import threading

STORE = os.path.expanduser("~/tag_map.json")

# A calibration is only meaningful if the tag was actually resolved well. A
# quad under this many pixels is mostly noise - the corner estimate wobbles
# and the area with it, so refuse to save one rather than store a bad target.
MIN_CALIB_AREA = 900


class TagMap:
    """Per-tag arrival signatures, persisted so a reboot keeps the calibration."""

    def __init__(self, path=STORE):
        self.path = path
        self._lock = threading.Lock()
        self.tags = {}
        self.load()

    def load(self):
        try:
            with open(self.path) as f:
                raw = json.load(f)
            # JSON keys are strings; the rest of the code thinks in ints
            self.tags = {int(k): v for k, v in raw.items()}
            print(f"[tagmap] loaded {len(self.tags)} calibrated tags")
        except (OSError, ValueError):
            self.tags = {}
            print("[tagmap] no calibration yet")

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({str(k): v for k, v in self.tags.items()}, f, indent=2)
        os.replace(tmp, self.path)        # atomic: never a half-written map

    def calibrate(self, tag, tilt=None, label=None):
        """Record the CURRENT view of `tag` as its arrival signature.

        `tag` is the live dict from Vision: {"id", "cx_norm", "area"}.
        Returns (ok, message) - the message is what the GUI shows the user.
        """
        if not tag:
            return False, "no tag visible - hold one up to the camera"
        if tag["area"] < MIN_CALIB_AREA:
            return False, (f"tag too small ({int(tag['area'])} px) - "
                           "move closer or hold it steadier")
        with self._lock:
            tid = int(tag["id"])
            prev = self.tags.get(tid)
            self.tags[tid] = {
                "area": round(float(tag["area"]), 1),
                "cx": round(float(tag["cx_norm"]), 3),
                "tilt": tilt,
                "label": label or (prev or {}).get("label") or f"art piece {tid}",
            }
            self.save()
        verb = "recalibrated" if prev else "calibrated"
        return True, f"tag {tid} {verb} at {int(tag['area'])} px"

    def forget(self, tag_id):
        with self._lock:
            self.tags.pop(int(tag_id), None)
            self.save()

    def target(self, tag_id):
        """The saved signature for a tag, or None if never calibrated."""
        return self.tags.get(int(tag_id))

    def as_dict(self):
        """Shape the GUI polls - plain types only, ready for JSON."""
        return {str(k): v for k, v in self.tags.items()}
