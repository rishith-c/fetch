#!/usr/bin/env python3
"""
AUTOPILOT — "go to art piece N", run inside the GUI process.

It has to live in the GUI because only one process can hold the serial port
and only one can hold /dev/video0. A separate autonomous script would mean
stopping the GUI to demo, which is not a demo.

    press a tag button ──► Autopilot.go(id)
                              │
              ┌───────────────┴───────────────┐
         tag NOT visible                 tag visible
              │                               │
      sweep the camera,                strafe to centre it
      creep + avoid on sonar           (never spin: spinning
      until it comes into view          swings the camera off
              │                          the target)
              └───────────────┬───────────────┘
                              ▼
                    close enough -> ARRIVED, stop

States: idle -> searching -> approaching -> arrived (or aborted)

SAFETY, in priority order:
  1. abort() from the GUI STOP button kills it instantly
  2. the Uno's own front veto still blocks forward motion under 25 cm
  3. sonar readings here steer around things before the veto has to fire
  4. a hard timeout stops it wandering forever if the tag never appears
"""
import threading
import time

import crowd_nav

# Approach tuning. AREA_ARRIVED is in pixels^2 of the detected tag quad, which
# is a proxy for range: a 140 mm tag at ~0.6 m fills roughly this much of a
# 640x480 frame. Measured empirically beats a pose solve we can't calibrate.
AREA_ARRIVED = 14000
CENTRE_DEADBAND = 0.10        # |cx_norm| under this counts as centred
SEARCH_SPIN = 35              # gentle rotation while hunting for the tag
CREEP = 30
STRAFE = 45
LOST_GRACE = 1.5              # s of not seeing the tag before re-searching
DEFAULT_TIMEOUT = 90.0


ACTIVE_STATES = ("replaying", "searching", "approaching")


class Autopilot:
    def __init__(self, robot, vision, tilt_sweep=None, tag_map=None,
                 path_store=None):
        self.robot = robot
        self.vision = vision
        self.tilt = tilt_sweep          # kept None now the servo is gone
        # Calibrated arrival signatures. Without one we fall back to
        # AREA_ARRIVED, which is a guess at "about 0.6 m from a 140 mm tag";
        # with one the robot stops exactly where you parked it during
        # calibration, which is the whole point of the feature.
        self.tag_map = tag_map
        # Taught routes. With one, a run is REPLAY then visual servo; without
        # one it falls back to sweep-and-search, which only works if the tag
        # happens to be visible from the start.
        self.paths = path_store
        self.state = "idle"
        self.target = None
        self.detail = ""
        self._stop = threading.Event()
        self._thread = None

    # ---------- public ----------
    def go(self, tag_id, timeout=DEFAULT_TIMEOUT):
        self.abort()
        self._stop.clear()
        self.target = int(tag_id)
        self.state = "searching"
        self.detail = f"looking for tag {self.target}"
        self._thread = threading.Thread(
            target=self._run, args=(timeout,), daemon=True)
        self._thread.start()

    def abort(self):
        if self._thread and self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=2.0)
        self._stop.set()
        if self.state in ACTIVE_STATES:
            self.state = "aborted"
            self.detail = "stopped"

    @property
    def busy(self):
        return self.state in ACTIVE_STATES

    def status(self):
        return {"state": self.state, "target": self.target,
                "detail": self.detail}

    # ---------- the loop ----------
    def _replay(self):
        """Drive the taught route open-loop. Returns False if aborted.

        Sonar still interrupts: an obstacle that was not there during
        teaching must not be driven through just because the recording says
        forward. On a block we pause, let it clear, and resume the SAME
        segment rather than skipping it - skipping would shorten the path
        and land short.
        """
        route = self.paths.route(self.target) if self.paths else None
        if not route:
            return True                      # nothing taught; go straight to vision
        self.state = "replaying"
        total = sum(s[3] for s in route)
        done = 0.0
        for vx, vy, w, dt in route:
            if self._stop.is_set():
                return False
            self.detail = f"replaying route: {int(100 * done / total)}%"
            end = time.time() + dt
            while time.time() < end:
                if self._stop.is_set():
                    return False
                f = self.robot.sensors.get("f", 0)
                # 0 means no echo (or unplugged) - never treat that as an
                # obstacle, or a dead sensor would freeze every replay.
                blocked = vx > 0 and 3 <= f < 25
                if blocked:
                    self.robot.stop()
                    self.detail = f"paused: something at {f} cm"
                    end += 0.1               # give the time back, do not skip
                else:
                    self.robot.drive(vx, vy, w)
                time.sleep(0.05)
            done += dt
        self.robot.stop()
        return True

    def _run(self, timeout):
        t0 = time.time()
        last_seen = 0.0
        try:
            if not self._replay():
                return
            while not self._stop.is_set():
                if time.time() - t0 > timeout:
                    self.state, self.detail = "aborted", "timed out"
                    break

                tag = self.vision.tag if self.vision else None
                on_target = tag is not None and tag["id"] == self.target
                sonar = dict(self.robot.sensors)

                if on_target:
                    last_seen = time.time()
                    if self.tilt:
                        self.tilt.hold()
                    if self._approach(tag, sonar):
                        self.state, self.detail = "arrived", \
                            f"at tag {self.target}"
                        break
                else:
                    # brief blips are normal at the edge of the frame; only
                    # fall back to searching once it has really gone
                    if time.time() - last_seen > LOST_GRACE:
                        self._search(sonar)
                    else:
                        self.robot.drive(CREEP, 0, 0)

                time.sleep(0.1)
        finally:
            self.robot.stop()
            if self.state in ACTIVE_STATES:
                self.state = "aborted"

    def _goal(self):
        """Arrival signature for the current target: the calibrated view if
        there is one, otherwise the hardcoded fallback."""
        saved = self.tag_map.target(self.target) if self.tag_map else None
        if saved:
            return float(saved["area"]), float(saved.get("cx", 0.0)), True
        return float(AREA_ARRIVED), 0.0, False

    def _approach(self, tag, sonar):
        """Centre with a STRAFE, close with a creep. Returns True on arrival."""
        self.state = "approaching"
        goal_area, goal_cx, calibrated = self._goal()
        # Aim the tag at the offset it had during calibration, not at dead
        # centre - if you parked slightly to one side of the piece, that
        # offset IS part of the location you saved.
        x = tag["cx_norm"] - goal_cx
        area = tag["area"]
        close = area >= goal_area
        centred = abs(x) < CENTRE_DEADBAND
        self.detail = (f"tag {self.target}: {int(area)}/{int(goal_area)} px"
                       + ("" if calibrated else "  (uncalibrated)"))

        if close and centred:
            self.robot.stop()
            return True

        # Strafing rather than spinning is the whole reason for mecanum here:
        # rotating to correct would swing the camera off the tag and lose it.
        vy = 0 if centred else STRAFE * (1 if x > 0 else -1) * min(1.0, abs(x) * 2.5)
        vx = 0 if close else CREEP

        # sonar still outranks vision: it is a direct measurement
        f = sonar.get("f", 0)
        if 0 < f < 30:
            vx = 0
            self.detail = f"blocked at {f} cm, sidestepping"
        else:
            pct = min(100, int(100 * area / goal_area)) if goal_area else 0
        self.detail = (f"tag {self.target}: {pct}% there"
                       + ("" if calibrated else "  (uncalibrated)"))

        self.robot.drive(vx, vy, 0)
        return False

    def _search(self, sonar):
        """No sighting: sweep the camera and rotate slowly, avoiding obstacles."""
        self.state = "searching"
        if self.tilt:
            self.tilt.sweep()
        vx, vy, w = crowd_nav.decide(
            sonar,
            self.vision.zones if (self.vision and self.vision.fresh) else None,
            bool(self.vision and self.vision.fresh))
        # if the path is clear there is nothing to drive toward yet, so turn
        # on the spot to bring new parts of the room into the camera's view
        if (vx, vy, w) == (crowd_nav.CRUISE, 0, 0):
            vx, vy, w = 0, 0, SEARCH_SPIN
        self.detail = f"searching for tag {self.target}"
        self.robot.drive(vx, vy, w)


class TiltSweep:
    """Servo hunting pattern: arc while searching, freeze on a sighting."""
    ANGLES = [80, 95, 110, 95]
    DWELL = 0.9

    def __init__(self, robot, centre=95):
        self.robot = robot
        self.i = 0
        self.last = 0.0
        self.angle = centre
        self.robot.tilt(self.angle)

    def sweep(self):
        if time.time() - self.last < self.DWELL:
            return
        self.last = time.time()
        self.i = (self.i + 1) % len(self.ANGLES)
        self.angle = self.ANGLES[self.i]
        self.robot.tilt(self.angle)

    def hold(self):
        pass          # a sighting means the current angle is the right one


if __name__ == "__main__":
    # logic-only self test, no hardware
    class FakeBot:
        sensors = {"f": 0, "lf": 0, "rf": 0, "lr": 0, "rr": 0}
        last = None
        def drive(self, vx, vy=0, w=0): self.last = (vx, vy, w)
        def stop(self): self.last = (0, 0, 0)
        def tilt(self, a): pass

    class FakeVision:
        ok = True
        fresh = True
        zones = [1.0] * 5
        tag = None

    bot, vis = FakeBot(), FakeVision()
    ap = Autopilot(bot, vis)

    vis.tag = {"id": 3, "cx_norm": 0.6, "area": 2000}
    assert ap._approach(vis.tag, bot.sensors) is False
    assert bot.last[1] > 0, "tag right of centre -> strafe right"
    print(f"tag right      -> {bot.last}  strafes right, no spin")

    vis.tag = {"id": 3, "cx_norm": -0.6, "area": 2000}
    ap._approach(vis.tag, bot.sensors)
    assert bot.last[1] < 0
    print(f"tag left       -> {bot.last}  strafes left")

    vis.tag = {"id": 3, "cx_norm": 0.01, "area": 2000}
    ap._approach(vis.tag, bot.sensors)
    assert bot.last[0] > 0 and bot.last[1] == 0
    print(f"centred, far   -> {bot.last}  creeps forward")

    vis.tag = {"id": 3, "cx_norm": 0.01, "area": 99999}
    assert ap._approach(vis.tag, bot.sensors) is True
    print(f"centred, close -> ARRIVED")

    bot.sensors = {"f": 12, "lf": 0, "rf": 0, "lr": 0, "rr": 0}
    vis.tag = {"id": 3, "cx_norm": 0.5, "area": 2000}
    ap._approach(vis.tag, bot.sensors)
    assert bot.last[0] == 0, "obstacle must stop forward motion"
    print(f"obstacle 12cm  -> {bot.last}  forward blocked, still strafes")
    print("autopilot self-test OK")
