#!/usr/bin/env python3
"""
CHECKPOINT GRAPH - drive it once, name the spots, travel between them.

THE MODEL
---------
Nodes are places: "home", "0", "1", ... Edges are the driving between them,
stored as the exact commands you gave while teaching.

    home ──teach──> 0 ──teach──> 1 ──teach──> 2

You never tell it a coordinate and you never have to show it a tag. You set
HOME, drive to a spot with the GUI, and press "mark as 0". Everything you
drove since the last mark becomes the edge home->0, and 0 becomes the new
"you are here". Drive on, press "mark as 1", and you have home->0->1.

TRAVELLING
----------
Edges run both ways. To go backwards along one we replay its segments in
reverse order with every velocity negated - valid here because the robot is
holonomic: -vx really is the exact opposite motion of +vx, which is not true
of a car. So from 2 you can reach home by reversing 1->2 then 0->1 then
home->0, and a breadth-first search finds the shortest chain between any two
nodes.

WHAT "CURRENT" MEANS AND HOW IT LIES
------------------------------------
`current` is where the robot BELIEVES it is - updated when a trip finishes,
not measured. Carry the robot somewhere by hand and the belief is wrong, and
the next trip drives a correct route from the wrong place. Press Set HOME (or
re-mark a node) to tell it the truth again. That is the price of having no
encoders, and it is why the physical HOME tape matters.

DRIFT
-----
Replay is open-loop, so each edge adds error - a few percent of its length,
plus heading. Short hops between adjacent checkpoints stay tight; a long
chain accumulates. Teaching checkpoints every couple of metres keeps each
edge short, which is the whole reason to have a graph instead of one long
route from home to everywhere.
"""
import json
import os
import threading
import time
from collections import deque

STORE = os.path.expanduser("~/checkpoints.json")

MERGE_EPS = 1.0          # percent; smaller differences are the same command
MIN_SEG = 0.05           # s; shorter is a keypress bounce
MAX_SEG = 30.0           # s; longer is a stuck key
MAX_SEGMENTS = 600
HOME = "home"


def _rev(segments):
    """The same drive, backwards: reverse the order, negate every velocity."""
    return [[-vx, -vy, -w, dt] for vx, vy, w, dt in reversed(segments)]


class CheckpointMap:
    def __init__(self, path=STORE):
        self.path = path
        self._lock = threading.Lock()
        self.nodes = {}          # id -> {"label": str}
        self.edges = {}          # "a>b" -> [[vx, vy, w, dt], ...]
        self.current = None      # where we believe the robot is
        self.armed = False       # recording driving into the next mark
        self._segs = []
        self._cur = None
        self._t0 = 0.0
        self.load()

    # ---------- persistence ----------
    def load(self):
        try:
            with open(self.path) as f:
                d = json.load(f)
            self.nodes = d.get("nodes", {})
            self.edges = d.get("edges", {})
            self.current = d.get("current")
            print(f"[checkpoints] {len(self.nodes)} nodes, "
                  f"{len(self.edges)} edges, at {self.current}")
        except (OSError, ValueError):
            self.nodes, self.edges, self.current = {}, {}, None
            print("[checkpoints] empty map")

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"nodes": self.nodes, "edges": self.edges,
                       "current": self.current}, f, indent=2)
        os.replace(tmp, self.path)      # atomic; never a half-written map

    # ---------- teaching ----------
    def set_home(self):
        """Declare the robot is on the HOME spot and start recording."""
        with self._lock:
            self.nodes.setdefault(HOME, {"label": "Home"})
            self.current = HOME
            self.armed = True
            self._segs, self._cur = [], None
            self.save()
        return True, "home set - now drive to a spot and mark it"

    def note(self, vx, vy, w):
        """Every manual drive command lands here while armed."""
        if not self.armed:
            return
        now = time.time()
        with self._lock:
            if (self._cur is not None
                    and abs(self._cur[0] - vx) < MERGE_EPS
                    and abs(self._cur[1] - vy) < MERGE_EPS
                    and abs(self._cur[2] - w) < MERGE_EPS):
                return                              # same key still held
            self._close(now)
            self._cur, self._t0 = (vx, vy, w), now

    def _close(self, now):
        """Bank the segment that just ended. Caller holds the lock."""
        if self._cur is None:
            return
        dt = now - self._t0
        vx, vy, w = self._cur
        moving = abs(vx) > MERGE_EPS or abs(vy) > MERGE_EPS or abs(w) > MERGE_EPS
        if moving and MIN_SEG <= dt <= MAX_SEG and len(self._segs) < MAX_SEGMENTS:
            self._segs.append([round(vx, 1), round(vy, 1), round(w, 1),
                               round(dt, 3)])

    def mark(self, node, label=None):
        """Name where the robot is standing, and bank the drive that got here."""
        node = str(node)
        if self.current is None:
            return False, "set home first"
        if node == self.current:
            return False, f"already at {node}"
        with self._lock:
            self._close(time.time())
            segs = list(self._segs)
            if not segs:
                return False, "no driving recorded - drive there first"
            self.nodes.setdefault(node, {})["label"] = (
                label or self.nodes.get(node, {}).get("label") or f"Tag {node}")
            self.edges[f"{self.current}>{node}"] = segs
            frm = self.current
            self.current = node          # standing here now
            self._segs, self._cur = [], None
            self.armed = True            # keep recording toward the next mark
            self.save()
        secs = sum(s[3] for s in segs)
        return True, f"{frm} -> {node} saved ({len(segs)} moves, {secs:.0f}s)"

    def set_current(self, node):
        """Correct the belief without re-teaching - 'it is actually here'."""
        node = str(node)
        if node not in self.nodes:
            return False, f"{node} is not a checkpoint yet"
        with self._lock:
            self.current = node
            self._segs, self._cur = [], None
            self.armed = True
            self.save()
        return True, f"now at {node}"

    def forget(self, node):
        node = str(node)
        with self._lock:
            self.nodes.pop(node, None)
            for k in [k for k in self.edges if node in k.split(">")]:
                del self.edges[k]
            if self.current == node:
                self.current = None
            self.save()

    # ---------- travelling ----------
    def neighbours(self, node):
        """(next_node, segments) for every edge usable from `node`, either way."""
        out = []
        for key, segs in self.edges.items():
            a, b = key.split(">")
            if a == node:
                out.append((b, segs))
            elif b == node:
                out.append((a, _rev(segs)))      # drive the edge backwards
        return out

    def plan(self, target, frm=None):
        """Shortest chain of segment-lists from `frm` to `target`.

        Returns (legs, error). legs is a list of segment-lists to replay in
        order; error is a human-readable reason when there is no route.
        """
        frm = frm or self.current
        target = str(target)
        if frm is None:
            return None, "robot position unknown - press Set HOME"
        if target not in self.nodes:
            return None, f"{target} has not been taught yet"
        if frm == target:
            return [], None                      # already there

        # BFS: every edge counts the same, so this is the fewest hops.
        prev = {frm: None}
        q = deque([frm])
        while q:
            cur = q.popleft()
            if cur == target:
                break
            for nxt, segs in self.neighbours(cur):
                if nxt not in prev:
                    prev[nxt] = (cur, segs)
                    q.append(nxt)
        if target not in prev:
            return None, f"no taught route from {frm} to {target}"

        legs, node = [], target
        while prev[node] is not None:
            parent, segs = prev[node]
            legs.append(segs)
            node = parent
        legs.reverse()
        return legs, None

    # ---------- reporting ----------
    def as_dict(self):
        return {
            "current": self.current,
            "nodes": {k: {"label": v.get("label", k)} for k, v in self.nodes.items()},
            "edges": [{"from": k.split(">")[0], "to": k.split(">")[1],
                       "moves": len(v), "secs": round(sum(s[3] for s in v), 1)}
                      for k, v in self.edges.items()],
            "pending": len(self._segs),
        }
