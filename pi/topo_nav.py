#!/usr/bin/env python3
"""Marker-to-marker navigation for the controlled FETCH demo corridor.

The phone QR selects a fixed checkpoint. The robot follows a directed graph of
AprilTag sightings. Every graph edge means: from the stopped pose at A, the
camera can acquire B and the straight segment A->B has been physically cleared.
This is deliberately not SLAM and is not general public-mall navigation.
"""

import argparse
import json
import time
from collections import deque


class TopoMap:
    def __init__(self, adj=None, names=None):
        self.adj = {int(k): {int(v) for v in values}
                    for k, values in (adj or {}).items()}
        referenced = {n for values in self.adj.values() for n in values}
        for node in referenced:
            self.adj.setdefault(node, set())
        self.names = {int(k): str(v) for k, v in (names or {}).items()}

    def add_edge(self, start, goal):
        """Add one verified, directed line-of-sight segment."""
        start, goal = int(start), int(goal)
        self.adj.setdefault(start, set()).add(goal)
        self.adj.setdefault(goal, set())

    def add_bidirectional_edge(self, a, b):
        self.add_edge(a, b)
        self.add_edge(b, a)

    def path(self, start, goal):
        start, goal = int(start), int(goal)
        if start == goal:
            return []
        if start not in self.adj or goal not in self.adj:
            return None
        seen = {start}
        queue = deque([(start, [])])
        while queue:
            node, route = queue.popleft()
            for nxt in sorted(self.adj[node]):
                if nxt in seen:
                    continue
                candidate = route + [nxt]
                if nxt == goal:
                    return candidate
                seen.add(nxt)
                queue.append((nxt, candidate))
        return None

    def connected(self):
        """Require every checkpoint to reach every other checkpoint."""
        nodes = sorted(self.adj)
        if not nodes:
            return False, []
        unreachable = []
        for start in nodes:
            for goal in nodes:
                if self.path(start, goal) is None:
                    unreachable.append((start, goal))
        return not unreachable, unreachable

    def validate(self):
        errors = []
        for node, neighbours in self.adj.items():
            if node in neighbours:
                errors.append(f"self edge {node}->{node}")
        ok, unreachable = self.connected()
        if not ok:
            errors.append("unreachable routes: " + ", ".join(
                f"{a}->{b}" for a, b in unreachable[:12]))
        return errors

    def save(self, path):
        data = {
            "_README": "Directed graph: A lists every tag physically acquired from the stopped pose at A.",
            "names": {str(k): v for k, v in sorted(self.names.items())},
            "adj": {str(k): sorted(v) for k, v in sorted(self.adj.items())},
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    @staticmethod
    def load(path):
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return TopoMap(data.get("adj", {}), data.get("names", {}))


def discover(vision, drive, markers_expected=None, spin_steps=12, settle=0.35):
    """Interactively record directed visibility at each physical checkpoint."""
    result = TopoMap()
    print("Park at each checkpoint. FETCH will rotate and record visible tags.")
    try:
        while True:
            value = input("Checkpoint ID (or done): ").strip()
            if value.lower() in {"", "done", "q"}:
                break
            here = int(value)
            seen = set()
            result.adj.setdefault(here, set())
            for index in range(spin_steps):
                drive.rotate_step(360.0 / spin_steps)
                time.sleep(settle)
                seen.update(mid for mid in vision.visible_ids() if mid != here)
                print(f"  {index + 1}/{spin_steps}: {sorted(seen)}", end="\r")
            print()
            for marker in seen:
                result.add_edge(here, marker)
            print(f"  directed edges from {here}: {sorted(seen)}")
    except KeyboardInterrupt:
        drive.stop()
        print("\nDiscovery stopped")
    errors = result.validate()
    if errors:
        print("MAP NOT READY:")
        for error in errors:
            print(" -", error)
    else:
        print("Map is strongly connected; every checkpoint can reach every other.")
    return result


class TopoNav:
    ARRIVE_FRONT_CM = 65
    ARRIVE_FRONT_TOLERANCE_CM = 12
    ARRIVE_AREA_FRACTION = 0.010
    ARRIVE_CENTER_OFFSET = 0.22
    ARRIVE_HOLD_SECONDS = 0.35
    APPROACH_MM_S = 140.0
    SEARCH_OMEGA_DEG_S = 45.0
    TURN_GAIN_DEG_S = 95.0
    CENTER_DEADBAND = 0.05
    SLOW_OFFSET = 0.30
    CONTROL_PERIOD_S = 0.05
    HOP_TIMEOUT_S = 45.0
    BLOCKED_CONFIRM_S = 0.40

    def __init__(self, tmap, vision, drive, telemetry):
        self.map = tmap
        self.vision = vision
        self.drive = drive
        self.telemetry = telemetry
        self.at = None
        self.state = "IDLE"
        self.cancelled = False
        self.last_error = None

    def cancel(self):
        self.cancelled = True
        self.state = "CANCELLED"
        self.drive.stop()

    def _health_check(self):
        if self.cancelled:
            raise RuntimeError("cancelled")
        if not self.vision.fresh():
            raise RuntimeError("camera frames are stale")
        if not self.telemetry.fresh():
            raise RuntimeError("Uno telemetry is stale")

    def go(self, goal):
        goal = int(goal)
        self.cancelled = False
        self.last_error = None
        self._health_check()
        if self.at is None:
            self.at = self._where_am_i()
            if self.at is None:
                self.at = self._search_any()
        route = self.map.path(self.at, goal)
        if route is None:
            self.last_error = f"no route {self.at}->{goal}"
            return False
        if not route:
            self.drive.stop()
            self.state = "ARRIVED"
            return True
        for target in route:
            if not self._hop_to(target):
                return False
            self.at = target
        self.state = "ARRIVED"
        self.drive.stop()
        return True

    def _where_am_i(self):
        detections = self.vision.visible_detections()
        valid = [d for d in detections if d["id"] in self.map.adj]
        return max(valid, key=lambda d: d["area_fraction"])["id"] if valid else None

    def _search_any(self, timeout=8.0):
        self.state = "LOCALIZING"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._health_check()
            checkpoint = self._where_am_i()
            if checkpoint is not None:
                self.drive.stop()
                return checkpoint
            if self.telemetry.estop():
                self.drive.stop()
                raise RuntimeError("obstacle prevents localization rotation")
            self.drive.cmd(0, 0, self.SEARCH_OMEGA_DEG_S)
            time.sleep(self.CONTROL_PERIOD_S)
        self.drive.stop()
        raise RuntimeError("no checkpoint tag acquired")

    def _arrival_candidate(self, detection, front_cm):
        return (
            front_cm > 0
            and abs(front_cm - self.ARRIVE_FRONT_CM) <= self.ARRIVE_FRONT_TOLERANCE_CM
            and abs(detection["offset"]) <= self.ARRIVE_CENTER_OFFSET
            and detection["area_fraction"] >= self.ARRIVE_AREA_FRACTION
        )

    def _hop_to(self, target):
        deadline = time.monotonic() + self.HOP_TIMEOUT_S
        arrival_since = None
        blocked_since = None
        self.state = "SEARCHING"

        while time.monotonic() < deadline:
            self._health_check()
            detection = self.vision.detect(target)
            front_cm = self.telemetry.front_cm()

            if detection is None:
                arrival_since = None
                if self.telemetry.estop():
                    self.drive.stop()
                    raise RuntimeError("obstacle prevents marker search")
                self.state = "SEARCHING"
                self.drive.cmd(0, 0, self.SEARCH_OMEGA_DEG_S)
                time.sleep(self.CONTROL_PERIOD_S)
                continue

            if self._arrival_candidate(detection, front_cm):
                self.drive.stop()
                arrival_since = arrival_since or time.monotonic()
                if time.monotonic() - arrival_since >= self.ARRIVE_HOLD_SECONDS:
                    return True
                time.sleep(self.CONTROL_PERIOD_S)
                continue
            arrival_since = None

            # A close sonar return without the large, centred destination tag
            # is an obstacle, not arrival. Never convert a bag into success.
            if 0 < front_cm <= 60:
                self.drive.stop()
                blocked_since = blocked_since or time.monotonic()
                if time.monotonic() - blocked_since >= self.BLOCKED_CONFIRM_S:
                    raise RuntimeError("route blocked before destination")
                time.sleep(self.CONTROL_PERIOD_S)
                continue
            blocked_since = None

            offset = detection["offset"]
            omega = 0.0 if abs(offset) < self.CENTER_DEADBAND else \
                max(-80.0, min(80.0, -offset * self.TURN_GAIN_DEG_S))
            vx = self.APPROACH_MM_S if abs(offset) < self.SLOW_OFFSET else \
                self.APPROACH_MM_S * 0.35
            self.state = "APPROACHING"
            self.drive.cmd(vx, 0, omega)
            time.sleep(self.CONTROL_PERIOD_S)

        self.drive.stop()
        self.last_error = f"timeout approaching checkpoint {target}"
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", default="topo_map.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        print("Run topo_server.py for navigation or use --check to validate a map.")
        return
    tmap = TopoMap.load(args.map)
    for node in sorted(tmap.adj):
        print(f"{node} -> {sorted(tmap.adj[node])}")
    errors = tmap.validate()
    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit(1)
    print("CONNECTED: every directed checkpoint route is reachable")


if __name__ == "__main__":
    main()
