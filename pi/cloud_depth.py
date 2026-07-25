#!/usr/bin/env python3
"""
Cloud depth client — asks the Modal service for 5-zone clearance from a frame.

STRICTLY ADVISORY. Runs in a background thread at ~2-3 Hz; the drive loop
reads .zones whenever it wants and NEVER blocks on the network. If WiFi dies
the robot keeps working on sonars alone (zones goes stale -> marked invalid).

Usage:
    depth = CloudDepth("https://<user>--fetch-depth-web.modal.run", camera_cap)
    depth.start()
    ...
    if depth.valid:   z = depth.zones   # [L, CL, C, CR, R] 0..1, 1 = clear
"""
import threading
import time

import cv2
import requests


class CloudDepth:
    def __init__(self, url, cap, period=0.35, timeout=1.2):
        self.url, self.cap = url, cap
        self.period, self.timeout = period, timeout
        self.zones = [1.0] * 5
        self.latency_ms = None
        self._stamp = 0.0
        self._stop = threading.Event()
        self._t = None

    @property
    def valid(self):
        return (time.time() - self._stamp) < 1.5     # stale > 1.5 s = ignore

    def start(self):
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            t0 = time.time()
            ok, frame = self.cap.read()
            if ok:
                small = cv2.resize(frame, (518, 291))
                ok2, jpg = cv2.imencode(".jpg", small,
                                        [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok2:
                    try:
                        r = requests.post(self.url, data=jpg.tobytes(),
                                          timeout=self.timeout,
                                          headers={"Content-Type":
                                                   "application/octet-stream"})
                        if r.ok:
                            j = r.json()
                            self.zones = j["zones"]
                            self.latency_ms = round((time.time()-t0)*1000)
                            self._stamp = time.time()
                    except requests.RequestException:
                        pass                          # advisory: fail silent
            dt = self.period - (time.time() - t0)
            if dt > 0:
                time.sleep(dt)


if __name__ == "__main__":
    import sys
    url = sys.argv[1]
    cap = cv2.VideoCapture(0)
    d = CloudDepth(url, cap)
    d.start()
    while True:
        time.sleep(0.5)
        print(f"valid={d.valid} zones={d.zones} rtt={d.latency_ms}ms")
