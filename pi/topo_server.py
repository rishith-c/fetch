#!/usr/bin/env python3
"""FETCH checkpoint server: iPhone QR destination -> AprilTag route -> Uno."""

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import serial

from topo_nav import TopoMap, TopoNav


class AprilTagVision:
    def __init__(self, camera=0, width=1280, height=720):
        self.cap = cv2.VideoCapture(camera)
        # MJPG commonly allows USB webcams to sustain 1280x720 on a Pi without
        # silently falling back due to USB bandwidth.
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            raise RuntimeError(f"camera {camera} did not open")
        if not hasattr(cv2, "aruco"):
            raise RuntimeError("OpenCV ArUco/AprilTag support is not installed")
        self.dictionary = cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_APRILTAG_36h11)
        if hasattr(cv2.aruco, "DetectorParameters"):
            self.params = cv2.aruco.DetectorParameters()
        else:  # OpenCV 4.6 compatibility on older Raspberry Pi OS images
            self.params = cv2.aruco.DetectorParameters_create()
        self.detector = (cv2.aruco.ArucoDetector(self.dictionary, self.params)
                         if hasattr(cv2.aruco, "ArucoDetector") else None)
        self.lock = threading.Lock()
        self.latest = {}
        self.last_frame_at = 0.0
        self.frame_width = 0
        self.frame_height = 0
        self.ok = False
        self.running = True
        self.thread = threading.Thread(target=self._capture, daemon=True)
        self.thread.start()

    def _capture(self):
        while self.running:
            ok, frame = self.cap.read()
            now = time.monotonic()
            if not ok or frame is None:
                with self.lock:
                    self.ok = False
                    self.latest = {}
                time.sleep(0.05)
                continue
            if self.detector is not None:
                corners, ids, _ = self.detector.detectMarkers(frame)
            else:
                corners, ids, _ = cv2.aruco.detectMarkers(
                    frame, self.dictionary, parameters=self.params)
            found = {}
            height, width = frame.shape[:2]
            frame_area = float(width * height)
            if ids is not None:
                for corner, raw_id in zip(corners, ids.flatten()):
                    points = corner.reshape(4, 2)
                    center_x = float(points[:, 0].mean())
                    area = abs(float(cv2.contourArea(points)))
                    marker_id = int(raw_id)
                    candidate = {
                        "id": marker_id,
                        "offset": max(-1.0, min(1.0,
                            (center_x - width / 2.0) / (width / 2.0))),
                        "area_fraction": area / frame_area,
                        "seen_at": now,
                    }
                    # If duplicate IDs are visible on a multi-face checkpoint,
                    # follow the larger/nearer face.
                    if (marker_id not in found or
                            candidate["area_fraction"] > found[marker_id]["area_fraction"]):
                        found[marker_id] = candidate
            with self.lock:
                self.latest = found
                self.last_frame_at = now
                self.frame_width = width
                self.frame_height = height
                self.ok = True

    def fresh(self, max_age=0.50):
        with self.lock:
            return self.ok and time.monotonic() - self.last_frame_at <= max_age

    def visible_detections(self):
        with self.lock:
            if time.monotonic() - self.last_frame_at > 0.50:
                return []
            return [dict(item) for item in self.latest.values()]

    def resolution_ok(self):
        with self.lock:
            return self.frame_width >= 1280 and self.frame_height >= 720

    def resolution(self):
        with self.lock:
            return [self.frame_width, self.frame_height]

    def visible_ids(self):
        return [item["id"] for item in self.visible_detections()]

    def detect(self, marker_id):
        with self.lock:
            if time.monotonic() - self.last_frame_at > 0.50:
                return None
            item = self.latest.get(int(marker_id))
            return dict(item) if item else None

    def close(self):
        self.running = False
        self.cap.release()


class UnoDriveTelemetry:
    PACKET_FIELDS = 7  # S + five distances + estop

    def __init__(self, port, baud=115200):
        self.ser = serial.Serial(port, baud, timeout=0.10)
        self.lock = threading.Lock()
        self._sonar = [0, 0, 0, 0, 0]
        self._estop = True
        self.last_packet_at = 0.0
        self.running = True
        time.sleep(2.0)  # Uno R4 may reset when USB CDC opens
        self.ser.reset_input_buffer()
        self.thread = threading.Thread(target=self._receive, daemon=True)
        self.thread.start()

    @staticmethod
    def parse_packet(line):
        parts = line.split()
        if len(parts) != UnoDriveTelemetry.PACKET_FIELDS or parts[0] != "S":
            return None
        try:
            values = [int(value) for value in parts[1:]]
        except ValueError:
            return None
        if any(value < 0 or value > 400 for value in values[:5]):
            return None
        if values[5] not in (0, 1):
            return None
        return values[:5], bool(values[5])

    def _receive(self):
        while self.running:
            try:
                line = self.ser.readline().decode("ascii", errors="ignore").strip()
                parsed = self.parse_packet(line)
                if parsed is None:
                    continue
                sonar, estop = parsed
                with self.lock:
                    self._sonar = sonar
                    self._estop = estop
                    self.last_packet_at = time.monotonic()
            except (OSError, serial.SerialException):
                time.sleep(0.05)

    def fresh(self, max_age=0.50):
        with self.lock:
            return time.monotonic() - self.last_packet_at <= max_age

    def sonar_cm(self):
        with self.lock:
            return list(self._sonar)

    def front_cm(self):
        return self.sonar_cm()[0]

    def estop(self):
        with self.lock:
            return self._estop

    def cmd(self, vx, vy, omega):
        vx = max(-250.0, min(250.0, float(vx)))
        vy = max(-250.0, min(250.0, float(vy)))
        omega = max(-120.0, min(120.0, float(omega)))
        packet = f"V {vx:.1f} {vy:.1f} {omega:.1f}\n".encode("ascii")
        with self.lock:
            self.ser.write(packet)

    def stop(self):
        try:
            self.cmd(0, 0, 0)
        except (OSError, serial.SerialException):
            pass

    def rotate_step(self, degrees):
        direction = 1.0 if degrees >= 0 else -1.0
        omega = 45.0 * direction
        duration = abs(float(degrees)) / 45.0
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            if not self.fresh() or self.estop():
                self.stop()
                raise RuntimeError("cannot rotate: stale telemetry or obstacle stop")
            self.cmd(0, 0, omega)
            time.sleep(0.05)
        self.stop()

    def close(self):
        self.stop()
        self.running = False
        self.ser.close()


class Controller:
    PHONE_TIMEOUT_S = 2.0

    def __init__(self, nav, drive, vision):
        self.nav = nav
        self.drive = drive
        self.vision = vision
        self.lock = threading.Lock()
        self.state = "IDLE"
        self.goal = None
        self.error = None
        self.generation = 0
        self.last_phone_at = 0.0
        self.running = True
        threading.Thread(target=self._phone_watchdog, daemon=True).start()

    def preflight(self):
        if not self.vision.fresh():
            raise RuntimeError("camera is not producing fresh frames")
        if not self.vision.resolution_ok():
            raise RuntimeError("camera resolution is below required 1280x720")
        if not self.drive.fresh():
            raise RuntimeError("Uno telemetry is not fresh")
        if self.drive.estop():
            raise RuntimeError("robot obstacle stop is active")

    def heartbeat(self):
        with self.lock:
            self.last_phone_at = time.monotonic()

    def come(self, zone):
        zone = int(zone)
        if zone not in self.nav.map.adj:
            raise ValueError(f"checkpoint {zone} is not in the venue map")
        self.preflight()
        with self.lock:
            if self.state == "ROUTING":
                raise RuntimeError("FETCH is already moving")
            self.goal = zone
            self.state = "ROUTING"
            self.error = None
            self.last_phone_at = time.monotonic()
            self.generation += 1
            generation = self.generation
        self.nav.cancelled = False
        threading.Thread(target=self._run, args=(zone, generation), daemon=True).start()

    def _run(self, zone, generation):
        try:
            success = self.nav.go(zone)
            with self.lock:
                if generation == self.generation:
                    self.state = "ARRIVED" if success else "FAILED"
                    if not success:
                        self.error = self.nav.last_error or "route failed"
        except Exception as error:
            self.drive.stop()
            with self.lock:
                if generation == self.generation:
                    self.state = "FAILED"
                    self.error = str(error)

    def cancel(self, reason=None):
        with self.lock:
            self.generation += 1
            self.state = "FAILED" if reason else "IDLE"
            self.error = reason
            if not reason:
                self.goal = None
        self.nav.cancel()
        self.drive.stop()

    def _phone_watchdog(self):
        while self.running:
            with self.lock:
                expired = (self.state == "ROUTING" and
                           time.monotonic() - self.last_phone_at > self.PHONE_TIMEOUT_S)
            if expired:
                self.cancel("phone heartbeat lost")
            time.sleep(0.10)

    def status(self):
        with self.lock:
            return {
                "state": self.state,
                "goal": self.goal,
                "at": self.nav.at,
                "navigation_state": self.nav.state,
                "sonar_cm": self.drive.sonar_cm(),
                "estop": self.drive.estop(),
                "telemetry_fresh": self.drive.fresh(),
                "camera_fresh": self.vision.fresh(),
                "camera_resolution": self.vision.resolution(),
                "error": self.error,
            }


def make_server(controller, host, port):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, code, value):
            body = json.dumps(value).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_json(self):
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > 4096:
                raise ValueError("invalid request size")
            return json.loads(self.rfile.read(size) or b"{}")

        def do_POST(self):
            try:
                data = self.read_json()
                if self.path == "/come":
                    controller.come(data["zone"])
                    self.send_json(202, controller.status())
                elif self.path == "/cancel":
                    controller.cancel()
                    self.send_json(200, controller.status())
                elif self.path == "/heartbeat":
                    controller.heartbeat()
                    self.send_json(200, controller.status())
                else:
                    self.send_json(404, {"error": "not found"})
            except (ValueError, KeyError, RuntimeError, json.JSONDecodeError) as error:
                self.send_json(400, {"error": str(error)})

        def do_GET(self):
            if self.path == "/status":
                controller.heartbeat()
                self.send_json(200, controller.status())
            else:
                self.send_json(404, {"error": "not found"})

        def log_message(self, *_):
            pass

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", default="topo_map.json")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--serial", default="/dev/ttyACM0")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--start-zone", type=int, required=True)
    args = parser.parse_args()

    tmap = TopoMap.load(args.map)
    errors = tmap.validate()
    if errors:
        raise SystemExit("invalid venue map: " + "; ".join(errors))
    if args.start_zone not in tmap.adj:
        raise SystemExit(f"start checkpoint {args.start_zone} is not in the map")

    vision = AprilTagVision(args.camera)
    drive = UnoDriveTelemetry(args.serial)
    nav = TopoNav(tmap, vision, drive, drive)
    nav.at = args.start_zone
    controller = Controller(nav, drive, vision)
    server = make_server(controller, args.host, args.port)
    print(f"FETCH ready on :{args.port}; checkpoints={sorted(tmap.adj)}; start={nav.at}")
    try:
        server.serve_forever()
    finally:
        controller.running = False
        drive.close()
        vision.close()


if __name__ == "__main__":
    main()
