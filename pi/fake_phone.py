#!/usr/bin/env python3
"""
FAKE PHONE — prove the robot comes, WITHOUT the iOS app.

Simulates the iPhone's 15Hz vector stream to fetch_relay, so you can test the
ENTIRE robot-side chain today:

    fake_phone -> HTTP /vector -> fetch_relay -> serial -> Uno -> wheels

If the robot behaves correctly under this script, the only untested link left
is the real app's ARKit tracking — everything on the robot is proven.

Run (on the Pi, with fetch_relay.py already running and the Uno plugged in):

  python3 fake_phone.py --approach     # person 4m ahead, 25deg left: robot
                                       # should TURN LEFT, then DRIVE FORWARD,
                                       # range winds down, ARRIVED at 0.6m -> stops
  python3 fake_phone.py --turn-right   # constant err -30deg: robot turns right
  python3 fake_phone.py --straight     # err 0, range 3m: drives straight
  python3 fake_phone.py --drop         # streams 2s then goes SILENT: robot must
                                       # STOP within ~0.6s (the LOST watchdog)

  --host 127.0.0.1  --port 8080        # where fetch_relay is listening

WHAT TO WATCH (the pass criteria):
  --approach   wheels turn toward the 'person', then forward; stop at arrive
  --drop       wheels STOP ~0.6s after the stream dies. If they keep spinning,
               the watchdog is broken — do not demo until fixed.

This is open-loop (canned ranges, the robot isn't really moving toward anyone),
so wheel DIRECTION is what you're checking, not distances.
"""
import argparse, json, time, urllib.request

def post(host, port, payload):
    req = urllib.request.Request(
        f"http://{host}:{port}/vector",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=1.0).read()
        return True
    except Exception as e:
        print(f"  !! POST failed: {e}")
        return False

def stream(host, port, vectors, hz=15):
    """vectors: iterable of (heading_err_deg, range_m). 15Hz like the phone."""
    seq = 0
    for err, rng in vectors:
        ok = post(host, port, {"heading_err_deg": err, "range_m": rng,
                               "bearing_deg": 0.0, "seq": seq})
        if ok and seq % 15 == 0:
            print(f"  t={seq//15:>3}s  err={err:+6.1f}deg  range={rng:4.2f}m")
        seq += 1
        time.sleep(1.0 / hz)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--approach", action="store_true")
    mode.add_argument("--straight", action="store_true")
    mode.add_argument("--turn-right", action="store_true")
    mode.add_argument("--drop", action="store_true")
    a = ap.parse_args()

    if a.approach:
        # person at 4m, 25deg to the LEFT. err decays (robot 'turns'), then
        # range walks down to arrival. ~20s total.
        vecs = []
        err, rng = 25.0, 4.0
        for _ in range(15 * 4):                      # 4s: turning phase
            err *= 0.96
            vecs.append((err, rng))
        while rng > 0.55:                            # approach phase
            rng -= 0.30 / 15                         # 0.3 m/s closing
            vecs.append((err, rng))
        vecs += [(0.0, 0.5)] * 30                    # hold at arrival 2s
        print("APPROACH: expect TURN LEFT -> FORWARD -> ARRIVED (stop) at 0.6m")
        stream(a.host, a.port, vecs)
    elif a.straight:
        print("STRAIGHT: err=0, range=3m held 10s — expect steady forward drive")
        stream(a.host, a.port, [(0.0, 3.0)] * 150)
    elif a.turn_right:
        print("TURN-RIGHT: err=-30deg held 10s — expect rotation to the right")
        stream(a.host, a.port, [(-30.0, 3.0)] * 150)
    elif a.drop:
        print("DROP: 2s of stream then SILENCE — wheels must stop within ~0.6s")
        stream(a.host, a.port, [(0.0, 3.0)] * 30)
        print("  ...stream dead. WATCH THE WHEELS: they must stop NOW.")
        time.sleep(3)

    print("done.")

if __name__ == "__main__":
    main()
