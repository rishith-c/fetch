#!/usr/bin/env python3
"""
FETCH drive — the Pi's control link to the Uno. Needs only pyserial.

Use as a library:
    from drive import Robot
    with Robot() as r:
        r.drive(60, 0, 0)      # forward 60%
        r.strafe_right(50)
        r.tilt(120)
        print(r.sensors)       # {'f': 52, 'lf': 110, ...} cm, 0 = no echo

Or from the shell (see __main__ at the bottom):
    python3 drive.py keys          # WASD teleop over SSH
    python3 drive.py crab          # crab circle, driven from the Pi
    python3 drive.py test          # move each direction 1 s, print sensors
    python3 drive.py sensors       # just stream distances

The Uno holds the safety: it stops on its own if we go quiet for 500 ms, so
this script re-sends the current velocity at 10 Hz while it holds a command.
"""
import glob
import sys
import threading
import time

import serial

BAUD = 115200


def find_port():
    """Uno R4 shows up as /dev/ttyACM* on the Pi, /dev/cu.usbmodem* on a Mac."""
    for pattern in ("/dev/ttyACM*", "/dev/ttyUSB*", "/dev/cu.usbmodem*"):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[0]
    raise IOError("No Uno found. Is it plugged in? Try: ls /dev/ttyACM*")


class Robot:
    def __init__(self, port=None, baud=BAUD):
        self.port = port or find_port()
        self.ser = serial.Serial(self.port, baud, timeout=0.1)
        time.sleep(2.0)                     # R4 resets when the port opens
        self.ser.reset_input_buffer()
        self.sensors = {k: 0 for k in ("f", "lf", "rf", "lr", "rr")}
        self._vel = (0, 0, 0)
        self._stop = threading.Event()
        self._rx = threading.Thread(target=self._reader, daemon=True)
        self._tx = threading.Thread(target=self._keepalive, daemon=True)
        self._rx.start()
        self._tx.start()

    # ---------- background threads ----------
    def _reader(self):
        while not self._stop.is_set():
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
            except Exception:
                break
            if line.startswith("us "):
                for tok in line[3:].split():
                    if "=" in tok:
                        k, v = tok.split("=", 1)
                        if k in self.sensors and v.lstrip("-").isdigit():
                            self.sensors[k] = int(v)

    def _keepalive(self):
        """Uno kills the motors if v goes quiet 500 ms — refresh at 10 Hz."""
        while not self._stop.is_set():
            vx, vy, w = self._vel
            if (vx, vy, w) != (0, 0, 0):
                self._send(f"v {vx:.0f} {vy:.0f} {w:.0f}")
            time.sleep(0.1)

    def _send(self, msg):
        self.ser.write((msg + "\n").encode())

    # ---------- commands ----------
    def drive(self, vx, vy=0, w=0):
        """vx forward, vy right, w clockwise. Each -100..100."""
        self._vel = (vx, vy, w)
        self._send(f"v {vx:.0f} {vy:.0f} {w:.0f}")

    def stop(self):
        """Emergency stop. Sent twice: the first byte breaks any routine
        running on the Uno (crab circle), the second is parsed as the stop
        command itself."""
        self._vel = (0, 0, 0)
        self._send("s")
        self._send("v 0 0 0")
        self._send("s")

    def forward(self, p=60):        self.drive(p, 0, 0)
    def back(self, p=60):           self.drive(-p, 0, 0)
    def strafe_left(self, p=60):    self.drive(0, -p, 0)
    def strafe_right(self, p=60):   self.drive(0, p, 0)
    def spin_left(self, p=60):      self.drive(0, 0, -p)
    def spin_right(self, p=60):     self.drive(0, 0, p)

    def motor(self, i, spd):
        """Drive ONE socket (0=X 1=Y 2=Z 3=A) at spd -100..100. Calibration
        only - bypasses the mecanum mix so a single wheel can be identified."""
        self._vel = (0, 0, 0)
        self._send(f"m {int(i)} {int(spd)}")

    def guard(self, on):
        """Arm/disarm the Uno's front-obstacle veto."""
        self._send(f"g {1 if on else 0}")

    def tilt(self, deg):
        self._send(f"t {int(max(0, min(180, deg)))}")

    def move_for(self, seconds, vx, vy=0, w=0):
        self.drive(vx, vy, w)
        time.sleep(seconds)
        self.stop()

    def crab_circle(self, seconds=None):
        """Run the circle ON THE UNO ('c'). Doing it here as a Python loop
        made STOP useless: the loop kept pushing new velocities a few ms
        after the stop landed. On the Uno, any incoming byte breaks the
        routine, so STOP wins immediately."""
        self._vel = (0, 0, 0)
        self._send("c")

    def close(self):
        try:
            self.stop()
        finally:
            self._stop.set()
            time.sleep(0.2)
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


# ----------------------------- CLI -----------------------------
def teleop(r):
    """WASD over SSH. Raw tty, no extra packages."""
    import termios
    import tty
    help_text = (
        "\n  w/s forward/back   a/d strafe   q/e spin   space stop\n"
        "  i/k camera tilt    p print sensors   c crab circle   x quit\n"
    )
    print(help_text)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    angle, spd = 90, 60
    try:
        tty.setcbreak(fd)
        while True:
            ch = sys.stdin.read(1).lower()
            if ch == "x":
                break
            elif ch == "w": r.forward(spd)
            elif ch == "s": r.back(spd)
            elif ch == "a": r.strafe_left(spd)
            elif ch == "d": r.strafe_right(spd)
            elif ch == "q": r.spin_left(spd)
            elif ch == "e": r.spin_right(spd)
            elif ch == " ": r.stop()
            elif ch == "i": angle = min(180, angle + 15); r.tilt(angle)
            elif ch == "k": angle = max(0, angle - 15); r.tilt(angle)
            elif ch == "p": print(f"  {r.sensors}")
            elif ch == "c": print("  crab circle..."); r.crab_circle()
            elif ch == "+": spd = min(100, spd + 10); print(f"  speed {spd}")
            elif ch == "-": spd = max(20, spd - 10); print(f"  speed {spd}")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        r.stop()


def selftest(r):
    for name, fn in [("forward", r.forward), ("back", r.back),
                     ("strafe left", r.strafe_left),
                     ("strafe right", r.strafe_right),
                     ("spin left", r.spin_left), ("spin right", r.spin_right)]:
        print(f"{name:14s} 1 s ... sensors {r.sensors}")
        fn(50); time.sleep(1.0); r.stop(); time.sleep(0.4)
    print("tilt sweep")
    for a in (60, 120, 90):
        r.tilt(a); time.sleep(0.5)
    print("done")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "keys"
    port = sys.argv[2] if len(sys.argv) > 2 else None
    with Robot(port) as robot:
        print(f"connected on {robot.port}")
        if mode == "keys":
            teleop(robot)
        elif mode == "crab":
            robot.crab_circle()
        elif mode == "test":
            selftest(robot)
        elif mode == "sensors":
            while True:
                time.sleep(0.3)
                print(robot.sensors)
        else:
            print(f"unknown mode {mode!r}: use keys | crab | test | sensors")
