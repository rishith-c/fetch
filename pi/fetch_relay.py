#!/usr/bin/env python3
"""
FETCH — Raspberry Pi relay.  PHONE-SEES-ROBOT architecture.

    phone --WiFi--> [this] --USB--> Uno R4 --> motors
                                     ^
                                     |__ ultrasonic veto lives on the Uno, so
                                         safety NEVER depends on WiFi.

WHY THIS ARCHITECTURE
    Every earlier design tried to make the ROBOT find the PERSON. That is
    impossible: no radio available to an iPhone gives DIRECTION (only distance),
    and the Pi's webcam can't tell you from anyone else.

    So it's inverted. A marker goes on the robot; YOUR PHONE tracks it with
    ARKit and ships the vector here. Your phone is 2.6x sharper than the Pi's
    webcam, has ARKit for free, and — crucially — it's YOURS, which solves
    "come to ME specifically" for nothing.

    Measured: 0.035 deg bearing accuracy. Camera homing arrives in ~19s vs
    ~13 MINUTES for BLE gradient homing.

THE CONTROL SIGNAL — read this before touching the math
    heading_err_deg, NOT bearing_deg.

    bearing says where the robot IS in your view. It says NOTHING about which
    way the robot is POINTED. Two robots at an identical 31.0deg bearing — one
    aimed at you, one aimed 60deg away — need OPPOSITE corrections. Steering on
    bearing is a bug; simulation proved it.

    heading_err = angle between the robot's facing and the robot->phone
    direction, derived from the MARKER'S ORIENTATION. Intuition: the marker is
    on the robot's front, so if you see it face-on, the robot is aimed at you.
    Turn until face-on, then drive.

Deps:  python3-serial only.   sudo apt install python3-serial
Run:   python3 fetch_relay.py --serial /dev/ttyACM0
"""
import argparse, json, threading, time, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    import serial
except ImportError:
    serial = None

# ---------------- tuning ----------------
APPROACH_SPEED = 240.0        # mm/s — under the firmware's 250 ceiling
TURN_GAIN      = 6.0          # omega units per degree of heading error
MAX_TURN       = 250.0
CENTER_DEADBAND_DEG = 4.0
SLOW_CONE_DEG  = 25.0         # badly misaligned -> creep, don't charge
ARRIVE_M       = 0.6
VECTOR_TIMEOUT = 0.6          # phone silent -> stop
CMD_HZ         = 20


class UnoLink:
    def __init__(self, port, baud=115200):
        self.ser = None
        self.luna_cm = 999
        self.estop = False
        if serial is None:
            print("[uno] pyserial missing — DRY RUN", file=sys.stderr)
            return
        self.ser = serial.Serial(port, baud, timeout=0.1)
        print(f"[uno] {port} open, waiting 2s for board reset...")
        time.sleep(2.0)          # opening the port RESETS the Uno. Classic gotcha.
        self.ser.reset_input_buffer()
        threading.Thread(target=self._rx, daemon=True).start()

    def _rx(self):
        while True:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
            except Exception:
                time.sleep(0.1); continue
            if line.startswith("S "):
                p = line.split()
                # S <luna> <zero-or-more ultrasonics> <estop>. The firmware
                # currently sends five sonics; accept either sensor config.
                if len(p) >= 3:
                    try:
                        self.luna_cm = int(p[1])
                        self.estop = p[-1] == "1"
                    except ValueError:
                        pass

    def drive(self, vx, vy, w):
        if self.ser:
            self.ser.write(f"V {vx:.1f} {vy:.1f} {w:.1f}\n".encode())

    def stop(self):
        self.drive(0, 0, 0)


class Relay:
    def __init__(self, uno):
        self.uno = uno
        self.lock = threading.Lock()
        self.vec = None                  # (heading_err_deg, range_m, bearing_deg)
        self.vec_at = 0.0
        self.active = False
        self.arrived = False
        self.state = "IDLE"
        self.last_seq = -1

    def on_vector(self, d):
        seq = int(d.get("seq", 0))
        with self.lock:
            if seq <= self.last_seq:      # drop out-of-order / duplicate
                return
            self.last_seq = seq
            # heading_err_deg is THE control signal. bearing_deg is UI-only.
            self.vec = (float(d["heading_err_deg"]), float(d["range_m"]),
                        float(d.get("bearing_deg", 0.0)))
            self.vec_at = time.time()
            if self.arrived:
                return                    # already there; don't re-launch
            self.active = True

    def cancel(self):
        with self.lock:
            self.active = False
            self.arrived = False
            self.vec = None
            self.last_seq = -1
            self.state = "IDLE"
        self.uno.stop()

    def status(self):
        with self.lock:
            v = self.vec
        return {"state": self.state, "luna_cm": self.uno.luna_cm,
                "estop": self.uno.estop,
                "heading_err": None if not v else round(v[0], 1),
                "range_m": None if not v else round(v[1], 2),
                "bearing": None if not v else round(v[2], 1)}

    def step(self):
        with self.lock:
            active, vec, vec_at, arrived = (self.active, self.vec,
                                            self.vec_at, self.arrived)
        # ARRIVED latches until cancel — otherwise it flips to IDLE next tick
        # and the app never gets to show "Here!".
        if arrived:
            self.state = "ARRIVED"
            return 0.0, 0.0, 0.0
        if not active or vec is None:
            self.state = "IDLE"
            return 0.0, 0.0, 0.0
        if time.time() - vec_at > VECTOR_TIMEOUT:
            self.state = "LOST"           # WiFi drop / phone pocketed -> stop
            return 0.0, 0.0, 0.0

        heading_err, rng, _bearing = vec
        if rng <= ARRIVE_M:
            with self.lock:
                self.active = False
                self.arrived = True
            self.state = "ARRIVED"
            return 0.0, 0.0, 0.0

        err = heading_err                 # NOT bearing. See module docstring.
        w = 0.0 if abs(err) < CENTER_DEADBAND_DEG else \
            max(-MAX_TURN, min(MAX_TURN, -err * TURN_GAIN))
        vx = APPROACH_SPEED if abs(err) < SLOW_CONE_DEG else APPROACH_SPEED * 0.3
        self.state = "APPROACH"
        return vx, 0.0, w

    def run(self):
        period = 1.0 / CMD_HZ
        while True:
            t0 = time.time()
            try:
                vx, vy, w = self.step()
                self.uno.drive(vx, vy, w)
            except Exception as e:
                print(f"[relay] {e}", file=sys.stderr)
                self.uno.stop()
            time.sleep(max(0, period - (time.time() - t0)))


def make_server(relay, port):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_POST(self):
            if self.path == "/vector":
                n = int(self.headers.get("Content-Length", 0))
                try:
                    relay.on_vector(json.loads(self.rfile.read(n) or b"{}"))
                    self._send(200, {"ok": True, "state": relay.state})
                except (ValueError, KeyError) as e:
                    self._send(400, {"error": str(e)})
            elif self.path == "/cancel":
                relay.cancel(); self._send(200, {"ok": True, "state": relay.state})
            else:
                self._send(404, {"error": "no"})

        def do_GET(self):
            if self.path == "/status":
                self._send(200, relay.status())
            else:
                self._send(404, {"error": "no"})

        def log_message(self, *a):
            pass

    srv = HTTPServer(("0.0.0.0", port), H)
    srv.timeout = 0.5
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="/dev/ttyACM0")
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()

    uno = UnoLink(a.serial)
    relay = Relay(uno)
    threading.Thread(target=relay.run, daemon=True).start()
    print(f"[fetch] relay on :{a.port}   POST /vector  POST /cancel  GET /status")
    srv = make_server(relay, a.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        uno.stop(); print("\n[fetch] stopped")


if __name__ == "__main__":
    main()
