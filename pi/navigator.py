#!/usr/bin/env python3
"""
NAVIGATOR - drive a planned chain of checkpoint edges.

Replaces the tag-chasing autopilot for checkpoint travel. There is no vision
in this loop at all: the route IS the plan, exactly as taught.

    go(target) -> plan the chain -> replay each leg -> update "you are here"

SAFETY
  - stop() aborts instantly and the wheels stop
  - any manual drive command cancels an active trip (the GUI does this)
  - sonar pauses forward motion when a reading is both close AND plausible;
    0 means "no echo" and never blocks, so a dead sensor cannot freeze a trip
  - `current` only advances after a leg finishes, so aborting mid-trip leaves
    the belief at the last checkpoint actually reached rather than claiming
    an arrival that never happened
"""
import threading
import time

VETO_NEAR_CM = 25
VETO_MIN_CM = 3          # below this the HC-SR04 is not measuring, it is lying


class Navigator:
    def __init__(self, robot, cmap):
        self.robot = robot
        self.map = cmap
        self.state = "idle"
        self.target = None
        self.detail = ""
        self._stop = threading.Event()
        self._thread = None

    # ---------- public ----------
    def go(self, target):
        legs, err = self.map.plan(target)
        if err:
            self.state, self.detail = "error", err
            return False, err
        if not legs:
            self.state, self.detail = "arrived", f"already at {target}"
            return True, self.detail

        self.abort()
        self._stop.clear()
        self.target = str(target)
        self.state = "driving"
        self.detail = f"heading to {self.target}"
        self._thread = threading.Thread(target=self._run, args=(legs,),
                                        daemon=True)
        self._thread.start()
        return True, f"driving to {self.target}"

    def abort(self):
        if self._thread and self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=3.0)
        self._stop.set()
        self.robot.stop()
        if self.state == "driving":
            self.state, self.detail = "stopped", "cancelled"

    @property
    def busy(self):
        return self.state == "driving"

    def status(self):
        return {"state": self.state, "target": self.target,
                "detail": self.detail, "at": self.map.current}

    # ---------- the loop ----------
    def _run(self, legs):
        total = sum(sum(s[3] for s in leg) for leg in legs)
        done = 0.0
        try:
            for leg in legs:
                for vx, vy, w, dt in leg:
                    if self._stop.is_set():
                        return
                    end = time.time() + dt
                    while time.time() < end:
                        if self._stop.is_set():
                            return
                        f = self.robot.sensors.get("f", 0)
                        if vx > 0 and VETO_MIN_CM <= f < VETO_NEAR_CM:
                            self.robot.stop()
                            self.detail = f"paused: obstacle at {f} cm"
                            end += 0.1          # give the time back, do not skip
                        else:
                            self.robot.drive(vx, vy, w)
                            self.detail = (f"heading to {self.target} - "
                                           f"{int(100 * done / total)}%")
                        time.sleep(0.05)
                    done += dt
            self.robot.stop()
            # Only now is the belief safe to advance: a trip that was aborted
            # partway must not claim the robot reached the far end.
            self.map.set_current(self.target)
            self.state = "arrived"
            self.detail = f"arrived at {self.target}"
        finally:
            self.robot.stop()
            if self.state == "driving":
                self.state, self.detail = "stopped", "interrupted"
