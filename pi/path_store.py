#!/usr/bin/env python3
"""
PATH STORE - teach and repeat.

THE IDEA (yours, and it is the right one)
-----------------------------------------
Park at HOME. Drive to an art piece by hand. The robot writes down every
command you gave it and how long you held it. Later it replays that exact
sequence to get back there.

    teach:   HOME --[you driving]--> art piece 3, turn, face the tag
             every (vx, vy, w, dt) recorded as you go

    repeat:  HOME --[replay the recording]--> roughly art piece 3
                                              then the TAG takes over
                                              and closes the last 30 cm

WHY THE TWO HALVES NEED EACH OTHER
----------------------------------
Replay alone is open-loop: no encoders means nothing checks whether the
wheels actually did what they were told. Mecanum wheels slip, the battery
sags, and the error compounds - over 5 m expect to land maybe 30-50 cm off,
with heading drift on top. Good enough to arrive in the neighbourhood, not
good enough to stop in front of a painting.

The tag alone cannot do it either: the camera has to SEE the tag before
visual servoing can start, and from across the room it is a few pixels or
out of frame entirely.

Together they cover each other exactly: replay gets close enough that the
tag is big in frame, then the tag corrects everything replay got wrong.
Drift never accumulates across runs because every run re-anchors on
something bolted to the wall.

WHAT HOME MEANS
---------------
Home is not a coordinate - we cannot know coordinates. Home is "the spot you
promised to start from". Every recording begins there, so every replay must
too. Set it once, mark the floor with tape, and put the robot back on that
tape before each run. If you start somewhere else, replay drives the shape
of the path from the wrong origin and lands somewhere wrong. The tag still
rescues it IF the tag ends up in view - which is why the tag half is not
optional.
"""
import json
import os
import threading
import time

STORE = os.path.expanduser("~/paths.json")

# A held key becomes many identical commands; collapsing them keeps the file
# small and replay smooth. A new segment starts when the command changes.
MERGE_EPS = 1.0          # percent difference that still counts as "same"
MIN_SEG = 0.05           # s - shorter than this is a keypress bounce, drop it
MAX_SEG = 30.0           # s - a single leg longer than this is a stuck key
MAX_SEGMENTS = 400       # runaway guard; ~10 min of normal driving


class PathStore:
    def __init__(self, path=STORE):
        self.path = path
        self._lock = threading.Lock()
        self.paths = {}          # tag_id -> [[vx, vy, w, dt], ...]
        self.home_set = False
        self.recording = None    # tag id currently being taught
        self._segs = []
        self._cur = None         # (vx, vy, w)
        self._t0 = 0.0
        self.load()

    # ---------- persistence ----------
    def load(self):
        try:
            with open(self.path) as f:
                raw = json.load(f)
            self.paths = {int(k): v for k, v in raw.get("paths", {}).items()}
            self.home_set = bool(raw.get("home_set"))
            print(f"[paths] loaded {len(self.paths)} taught routes")
        except (OSError, ValueError):
            self.paths, self.home_set = {}, False
            print("[paths] nothing taught yet")

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"home_set": self.home_set,
                       "paths": {str(k): v for k, v in self.paths.items()}},
                      f, indent=2)
        os.replace(tmp, self.path)

    # ---------- home ----------
    def set_home(self):
        """Declare the robot is standing on the start spot.

        Teaching a route from anywhere else makes that route meaningless, so
        this also refuses to leave a half-taught recording behind.
        """
        with self._lock:
            self.recording = None
            self._segs, self._cur = [], None
            self.home_set = True
            self.save()
        return True, "home set - mark this spot with tape"

    # ---------- teaching ----------
    def start_recording(self, tag_id):
        if not self.home_set:
            return False, "set home first, then drive from there"
        with self._lock:
            self.recording = int(tag_id)
            self._segs, self._cur, self._t0 = [], None, time.time()
        return True, f"recording route to tag {tag_id} - drive it now"

    def note(self, vx, vy, w):
        """Called on every manual drive command while teaching."""
        if self.recording is None:
            return
        now = time.time()
        with self._lock:
            same = (self._cur is not None
                    and abs(self._cur[0] - vx) < MERGE_EPS
                    and abs(self._cur[1] - vy) < MERGE_EPS
                    and abs(self._cur[2] - w) < MERGE_EPS)
            if same:
                return                       # still holding the same key
            self._close_segment(now)
            self._cur, self._t0 = (vx, vy, w), now

    def _close_segment(self, now):
        """Bank the segment that just ended. Caller holds the lock."""
        if self._cur is None:
            return
        dt = now - self._t0
        vx, vy, w = self._cur
        moving = abs(vx) > MERGE_EPS or abs(vy) > MERGE_EPS or abs(w) > MERGE_EPS
        # Pauses are real - you stopped to look - but replaying a stop just
        # wastes demo time, so only motion is kept.
        if moving and MIN_SEG <= dt <= MAX_SEG and len(self._segs) < MAX_SEGMENTS:
            self._segs.append([round(vx, 1), round(vy, 1), round(w, 1),
                               round(dt, 3)])

    def stop_recording(self):
        if self.recording is None:
            return False, "not recording"
        with self._lock:
            self._close_segment(time.time())
            tid, segs = self.recording, list(self._segs)
            self.recording = None
            self._segs, self._cur = [], None
            if not segs:
                return False, "nothing recorded - did the robot move?"
            self.paths[tid] = segs
            self.save()
        secs = sum(s[3] for s in segs)
        return True, f"route to tag {tid} saved: {len(segs)} moves, {secs:.0f}s"

    # ---------- reading back ----------
    def route(self, tag_id):
        return self.paths.get(int(tag_id))

    def forget(self, tag_id):
        with self._lock:
            self.paths.pop(int(tag_id), None)
            self.save()

    def as_dict(self):
        return {str(k): {"moves": len(v), "secs": round(sum(s[3] for s in v), 1)}
                for k, v in self.paths.items()}
