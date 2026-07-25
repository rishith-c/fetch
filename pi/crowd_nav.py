#!/usr/bin/env python3
"""
Crowd navigation layer — turns sonar + cloud-depth into MECANUM moves.

This is where the wheels earn their keep: a normal robot must stop-rotate-
drive-rotate around a person; a mecanum robot STRAFES past while still facing
its checkpoint, so the camera never loses the AprilTag.

Layering (fastest wins):
  1. Uno veto (0 ms, front sonar <25 cm)      -> hard stop, not our problem
  2. sonar belt (this, ~10 ms old data)       -> sidestep / wait decisions
  3. cloud depth zones (~350 ms old, advisory)-> pick WHICH side is opening up

decide(us, zones, valid) -> (vx, vy, w) modifier for the current drive command.
Pure function, unit-testable, no I/O.
"""

CRUISE = 60          # forward % while a segment is clear
CREEP = 30           # forward % while squeezing past something
STRAFE = 45          # sidestep %
NEAR = 45            # cm: something worth reacting to
CLEAR = 70           # cm: comfortably open


def decide(us, zones=None, zones_valid=False):
    """us: dict f/lf/rf/lr/rr in cm (0 = no echo = treat as open).
    Returns (vx, vy, w) percentages for the *next* command frame."""
    f, lf, rf = us.get("f", 0), us.get("lf", 0), us.get("rf", 0)
    blocked = 0 < f < NEAR
    l_open = (lf == 0 or lf > CLEAR)
    r_open = (rf == 0 or rf > CLEAR)

    # cloud depth breaks ties / spots gaps sonars can't (thin people, chairs)
    if zones_valid and zones:
        l_score = zones[0] + zones[1]
        r_score = zones[3] + zones[4]
    else:
        l_score = r_score = None

    if not blocked:
        # path ahead open — but lean away from a wall we're grazing
        vy = 0
        if 0 < lf < NEAR and r_open:
            vy = +STRAFE // 2          # drift right, keep heading
        elif 0 < rf < NEAR and l_open:
            vy = -STRAFE // 2
        return (CRUISE, vy, 0)

    # front blocked: choose a sidestep, never a spin (keep tag in view)
    if l_open and r_open:
        if l_score is not None and l_score != r_score:
            go_left = l_score > r_score
        else:
            go_left = (lf == 0 or (rf != 0 and lf >= rf))
        return (CREEP, -STRAFE, 0) if go_left else (CREEP, +STRAFE, 0)
    if l_open:
        return (CREEP, -STRAFE, 0)
    if r_open:
        return (CREEP, +STRAFE, 0)

    # boxed in (crowd): stop and wait — people move, walls don't
    return (0, 0, 0)


def align_on_tag(tag_x_norm, deadband=0.06):
    """Checkpoint fine-alignment, mecanum style: strafe until the AprilTag is
    centered instead of rotating (rotation would swing the camera off-target).
    tag_x_norm: tag center in image, -1 (left) .. +1 (right)."""
    if abs(tag_x_norm) < deadband:
        return (0, 0, 0)
    return (0, STRAFE * (1 if tag_x_norm > 0 else -1) * min(1.0, abs(tag_x_norm) * 2), 0)


if __name__ == "__main__":
    # tiny truth-table self-test
    cases = [
        ({"f": 0, "lf": 0, "rf": 0}, None, False, "open floor -> cruise"),
        ({"f": 30, "lf": 100, "rf": 100}, [0.2, 0.2, 0.1, 0.8, 0.9], True,
         "blocked, depth says right clearer -> strafe right"),
        ({"f": 30, "lf": 100, "rf": 20}, None, False, "blocked, right wall -> strafe left"),
        ({"f": 20, "lf": 20, "rf": 20}, None, False, "boxed in -> wait"),
        ({"f": 0, "lf": 30, "rf": 200}, None, False, "grazing left wall -> drift right"),
    ]
    for us, z, v, note in cases:
        print(f"{note:48s} -> {decide(us, z, v)}")
    assert decide({"f": 20, "lf": 20, "rf": 20}) == (0, 0, 0)
    assert decide({"f": 30, "lf": 100, "rf": 100}, [0.2,0.2,0.1,0.8,0.9], True)[1] > 0
    assert decide({"f": 30, "lf": 100, "rf": 20})[1] < 0
    print("crowd_nav self-test OK")
