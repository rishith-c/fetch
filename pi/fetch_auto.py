#!/usr/bin/env python3
"""
FETCH AUTO — the whole autonomous flow in one process.

    camera (picamera2) ─┬─► AprilTag detector ──► "which art piece am I at"
                        └─► floor/obstacle vision ──► steering bias
                                    │
    sonar belt (from the Uno) ──────┼──► crowd_nav.decide()
                                    ▼
                              drive.Robot ──USB──► Uno ──► wheels
                                    │
                              servo tilt: sweep to FIND a tag,
                                          then hold it centred

Run:
    python3 fetch_auto.py --scan            # stand still, just look and report
    python3 fetch_auto.py --goto 3          # drive to checkpoint 3
    python3 fetch_auto.py --wander          # drive with obstacle avoidance

Every stage degrades instead of failing:
  no camera   -> sonar-only driving, tag features disabled
  no tags     -> keeps sweeping the servo, keeps driving on sonar
  no sonar    -> vision-only, speed capped
This matters because the sonars have been intermittent and the camera is the
newest part of the stack; one missing input must never brick the robot.
"""
import argparse
import math
import sys
import threading
import time

sys.path.insert(0, "/home/varun")

from drive import Robot
import crowd_nav

# ---- optional imports, each guarded so the robot still runs without them ----
try:
    from picamera2 import Picamera2
    HAVE_PICAM = True
except Exception:
    HAVE_PICAM = False

try:
    import cv2
    import numpy as np
    HAVE_CV = True
except Exception:
    HAVE_CV = False

try:
    from pupil_apriltags import Detector
    HAVE_TAGS = True
except Exception:
    HAVE_TAGS = False


# --------------------------------------------------------------------------
class Vision:
    """Camera thread: AprilTags + a coarse obstacle estimate from the image.

    Runs at its own rate and publishes the latest result. The drive loop reads
    the attributes and never blocks on a frame.
    """

    def __init__(self, size=(640, 480), fps=10):
        self.size, self.period = size, 1.0 / fps
        self.ok = False
        self.tag = None            # {'id', 'cx_norm', 'area'} of the biggest tag
        self.zones = [1.0] * 5     # per-column clearance, 1 = clear
        self.frame_age = 999.0
        self.jpeg = None            # latest annotated frame, for the web view
        self._jlock = threading.Lock()
        self._stamp = 0.0
        self._stop = threading.Event()
        self.cam = None      # picamera2 handle
        self.cap = None      # cv2 VideoCapture handle
        self.kind = None     # 'usb' | 'csi'
        self.det = None

        if not HAVE_CV:
            print("[vision] cv2 unavailable - vision disabled")
            return

        # USB webcam first (cv2/V4L2), then CSI module (picamera2). The USB
        # path is tried first because a USB cam can be hot-plugged, so it is
        # the one most likely to have appeared since boot.
        for idx in (0, 1, 2):
            try:
                cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
                    cap.set(cv2.CAP_PROP_FOURCC,
                            cv2.VideoWriter_fourcc(*"MJPG"))   # 640x480@30 on USB2
                    ok, _ = cap.read()
                    if ok:
                        self.cap, self.kind, self.ok = cap, "usb", True
                        print(f"[vision] USB camera on /dev/video{idx}")
                        break
                cap.release()
            except Exception:
                pass

        if not self.ok and HAVE_PICAM:
            try:
                if Picamera2.global_camera_info():
                    self.cam = Picamera2()
                    self.cam.configure(self.cam.create_preview_configuration(
                        main={"format": "RGB888", "size": size}))
                    self.cam.start()
                    time.sleep(1.0)
                    self.kind, self.ok = "csi", True
                    print("[vision] CSI camera up")
            except Exception as e:
                print(f"[vision] picamera2 failed: {e}")

        if not self.ok:
            print("[vision] NO CAMERA FOUND - running sonar-only")
            return

        if HAVE_TAGS:
            # tag36h11 is the standard family; nthreads=2 leaves cores for
            # the drive loop and the web GUI on a 4-core Pi
            self.det = Detector(families="tag36h11", nthreads=2,
                                quad_decimate=2.0)
            print("[vision] apriltag detector ready")
        else:
            print("[vision] pupil_apriltags missing - tag nav disabled")

    @property
    def fresh(self):
        return self.ok and (time.time() - self._stamp) < 1.0

    def start(self):
        if self.ok:
            threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop.set()
        time.sleep(0.2)
        try:
            if self.cap is not None:
                self.cap.release()
            if self.cam is not None:
                self.cam.stop()
        except Exception:
            pass

    def _run(self):
        while not self._stop.is_set():
            t0 = time.time()
            try:
                if self.kind == "usb":
                    ok, frame = self.cap.read()
                    if not ok:
                        time.sleep(0.2); continue
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                else:
                    rgb = self.cam.capture_array()
                    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
                self._find_tag(gray)
                self._estimate_zones(gray)
                self._stamp = time.time()
                self._annotate(gray if self.kind != "usb" else frame)
            except Exception as e:
                print(f"[vision] frame error: {e}")
                time.sleep(0.3)
            dt = self.period - (time.time() - t0)
            if dt > 0:
                time.sleep(dt)

    def _annotate(self, img):
        """Draw what the robot is actually reasoning about, then JPEG it.
        Seeing the overlay is the fastest way to tell a real detection from
        a lucky one, and whether the zone bands line up with the obstacles."""
        vis = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        vis = vis.copy()
        h, w = vis.shape[:2]

        # obstacle zones as five bars along the bottom
        for i, z in enumerate(self.zones):
            x0, x1 = int(i * w / 5) + 2, int((i + 1) * w / 5) - 2
            bar = int((1.0 - z) * 46)
            colour = (60, 220, 90) if z > 0.6 else (
                     (40, 200, 240) if z > 0.35 else (60, 60, 240))
            cv2.rectangle(vis, (x0, h - 6 - bar), (x1, h - 6), colour, -1)
            cv2.rectangle(vis, (x0, h - 52), (x1, h - 6), (70, 70, 70), 1)

        if self.tag:
            cx = int((self.tag["cx_norm"] * (w / 2)) + w / 2)
            cv2.line(vis, (cx, 0), (cx, h - 56), (0, 215, 255), 2)
            cv2.putText(vis, f"TAG {self.tag['id']}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 215, 255), 2)
            cv2.putText(vis, f"x={self.tag['cx_norm']:+.2f}", (10, 56),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 215, 255), 1)
        else:
            cv2.putText(vis, "no tag", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150, 150, 150), 2)
        cv2.line(vis, (w // 2, 0), (w // 2, 12), (255, 255, 255), 1)   # centre

        ok, buf = cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 65])
        if ok:
            with self._jlock:
                self.jpeg = buf.tobytes()

    def latest_jpeg(self):
        with self._jlock:
            return self.jpeg

    def _find_tag(self, gray):
        if self.det is None:
            self.tag = None
            return
        hits = self.det.detect(gray)
        if not hits:
            self.tag = None
            return
        # biggest tag = nearest; that's the one worth steering to
        best = max(hits, key=lambda d: cv2.contourArea(
            d.corners.astype("float32")))
        w = gray.shape[1]
        self.tag = {
            "id": int(best.tag_id),
            "cx_norm": (best.center[0] - w / 2) / (w / 2),   # -1..+1
            "area": float(cv2.contourArea(best.corners.astype("float32"))),
        }

    def _estimate_zones(self, gray):
        """Cheap obstacle proxy without a depth model: near objects fill the
        lower frame with large, low-texture blobs. Sobel energy per column
        band is a decent stand-in and costs ~2 ms, so it runs on the Pi.
        High texture (floor detail far away) = clear; a flat close wall = low.
        """
        band = gray[int(gray.shape[0] * 0.55):, :]           # lower half only
        gx = cv2.Sobel(band, cv2.CV_16S, 1, 0, ksize=3)
        energy = np.abs(gx).mean(axis=0)
        cols = np.array_split(energy, 5)
        raw = np.array([c.mean() for c in cols], dtype="float32")
        # normalise against this frame's own max so lighting doesn't matter
        top = max(float(raw.max()), 1.0)
        self.zones = [round(float(v / top), 3) for v in raw]


# --------------------------------------------------------------------------
class CameraTilt:
    """Sweeps the servo to find a tag, then holds it vertically centred."""

    SWEEP = [70, 85, 100, 115, 100, 85]      # degrees, gentle arc
    DWELL = 0.8                              # seconds per sweep stop

    def __init__(self, robot):
        self.robot = robot
        self.angle = 90
        self.idx = 0
        self.last = 0.0
        self.robot.tilt(self.angle)

    def update(self, tag_seen):
        """Call often. Sweeps while nothing is seen; parks when a tag is."""
        if tag_seen:
            return                            # hold position on a sighting
        if time.time() - self.last < self.DWELL:
            return
        self.last = time.time()
        self.idx = (self.idx + 1) % len(self.SWEEP)
        self.angle = self.SWEEP[self.idx]
        self.robot.tilt(self.angle)


# --------------------------------------------------------------------------
def fuse(sonar, vision):
    """Combine sonar and vision into one (vx, vy, w) command.

    Sonar is authoritative for anything close - it is a direct measurement.
    Vision only breaks ties about WHICH way is more open, because the column
    estimate is coarse and can be fooled by texture.
    """
    zones = vision.zones if vision.fresh else None
    return crowd_nav.decide(sonar, zones, zones is not None)


def approach_tag(tag):
    """Centre a tag with a strafe, not a spin, so the camera keeps it in view.
    Returns (vx, vy, w) or None when we are close and centred."""
    if tag is None:
        return None
    _, vy, _ = crowd_nav.align_on_tag(tag["cx_norm"])
    close = tag["area"] > 12000               # ~arm's length for a 100 mm tag
    vx = 0 if close else crowd_nav.CREEP
    if close and vy == 0:
        return None                           # arrived
    return (vx, vy, 0)


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true",
                    help="stand still, report what the sensors and camera see")
    ap.add_argument("--wander", action="store_true",
                    help="drive with obstacle avoidance")
    ap.add_argument("--goto", type=int, metavar="TAG_ID",
                    help="drive until this AprilTag is centred and close")
    ap.add_argument("--seconds", type=float, default=60.0)
    args = ap.parse_args()

    vision = Vision()
    vision.start()

    with Robot() as bot:
        print(f"[drive] connected on {bot.port}")
        bot.guard(True)
        tilt = CameraTilt(bot)
        t0 = time.time()
        try:
            while time.time() - t0 < args.seconds:
                sonar = dict(bot.sensors)
                tag = vision.tag
                tilt.update(tag is not None)

                if args.scan:
                    z = [f"{v:.2f}" for v in vision.zones] if vision.fresh else "--"
                    t = f"id={tag['id']} x={tag['cx_norm']:+.2f}" if tag else "none"
                    print(f"sonar {sonar}  tilt {tilt.angle:3d}  zones {z}  tag {t}")
                    time.sleep(0.5)
                    continue

                cmd = None
                if args.goto is not None:
                    if tag and tag["id"] == args.goto:
                        cmd = approach_tag(tag)
                        if cmd is None:
                            print(f"[nav] arrived at tag {args.goto}")
                            break
                    else:
                        cmd = fuse(sonar, vision)      # explore until seen
                elif args.wander:
                    cmd = fuse(sonar, vision)

                if cmd:
                    bot.drive(*cmd)
                else:
                    bot.stop()
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\ninterrupted")
        finally:
            bot.stop()
            vision.stop()
            print("[drive] stopped")


if __name__ == "__main__":
    main()
