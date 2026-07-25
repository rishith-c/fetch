#!/usr/bin/env python3
"""
FETCH — A4988 Vref calculator.  "CHECK THE RESISTORS ON THE BOARD."

THE TRAP
    Vref = Imax * 8 * Rsense

    Rsense is NOT a property of the A4988 chip. It's two tiny current-sense
    resistors soldered on YOUR driver board, and vendors use different values.
    The SAME Vref gives DIFFERENT motor current depending on which board you have.

    Genuine Pololu A4988 : Rsense = 0.05 ohm   -> Vref = Imax * 0.40
    Many clones (BIQU..) : Rsense = 0.10 ohm   -> Vref = Imax * 0.80
    Some older clones    : Rsense = 0.20 ohm   -> Vref = Imax * 1.60

    Assume 0.100 when you actually have 0.050 and you set HALF the current you
    intended: weak motors, skipped steps, a robot that buzzes and crawls.
    Assume 0.050 when you have 0.100 and you set DOUBLE: cooked driver.

    This is the single most common reason a stepper build "just doesn't work",
    and it is invisible — nothing warns you.

HOW TO READ YOUR BOARD
    Look at the two small black SMD resistors right next to the trim pot,
    usually just below the chip. They are marked:

        R050  or  50   ->  0.050 ohm
        R100  or 100   ->  0.100 ohm
        R200  or 200   ->  0.200 ohm

    A phone macro shot helps — they are ~2mm long. BOTH should read the same.
    If you genuinely cannot read them, measure: see --explain.

Usage:
    python3 vref_calc.py --rated 1.7                 # show all Rsense cases
    python3 vref_calc.py --rated 1.7 --rsense 0.100  # your board
    python3 vref_calc.py --explain
"""
import argparse

DUTY = 0.75          # run drivers at ~70-85% of motor rating (heat)
BOARDS = [
    (0.050, "Pololu genuine / StepStick 'R050'"),
    (0.068, "some Watterott / SilentStepStick variants"),
    (0.100, "common clones 'R100' (most cheap 5-packs)"),
    (0.200, "older clones 'R200'"),
]


def vref(imax, rsense):
    return imax * 8.0 * rsense


def imax_from_vref(v, rsense):
    return v / (8.0 * rsense)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rated", type=float, default=1.7,
                   help="motor rated current per phase, from the motor label (A)")
    p.add_argument("--duty", type=float, default=DUTY,
                   help="fraction of rated to actually run (default 0.75)")
    p.add_argument("--rsense", type=float, default=None,
                   help="your board's sense resistor in ohms, if you know it")
    p.add_argument("--explain", action="store_true")
    a = p.parse_args()

    if a.explain:
        print(__doc__)
        print("""
IF YOU CANNOT READ THE MARKINGS
    1. Power the driver (motor DISCONNECTED).
    2. Multimeter: black probe on any GND pin, red probe on the trim pot's
       metal wiper. Read Vref.
    3. Connect ONE motor coil in series with the multimeter set to DC AMPS,
       command a slow continuous step, read the current.
    4. Rsense = Vread / (8 * Imeasured).  Round to the nearest of
       0.050 / 0.068 / 0.100 / 0.200.

    Safer alternative: start at the LOWEST Vref that moves the motor, then
    creep up. Under-current only means weak; over-current means smoke.
""")
        return

    target = a.rated * a.duty
    print("=" * 70)
    print("A4988 Vref — CHECK YOUR BOARD'S SENSE RESISTORS")
    print("=" * 70)
    print(f"  motor rated current   {a.rated:.2f} A/phase   (read it off the motor label)")
    print(f"  duty                  {a.duty:.0%}")
    print(f"  target driver current {target:.2f} A")
    print()

    if a.rsense:
        v = vref(target, a.rsense)
        print(f"  YOUR BOARD: Rsense = {a.rsense:.3f} ohm")
        print(f"  >>> SET Vref = {v:.3f} V  <<<")
        print()
        print("  Procedure (do this for ALL FOUR drivers, motors disconnected):")
        print("    1. power the shield's motor rail (or 12V bench supply)")
        print("    2. multimeter black -> any GND, red -> the trim pot's metal wiper")
        print(f"    3. turn the pot until it reads {v:.3f} V")
        print("    4. repeat on each driver — they will NOT match out of the box")
        print()
        print("  Include the 4th HAND-WIRED driver. It is the one people forget,")
        print("  and a mismatched 4th wheel makes the robot curve.")
        return

    print(f"  {'Rsense':>8} {'Vref to set':>12}   board")
    print("  " + "-" * 62)
    for rs, name in BOARDS:
        print(f"  {rs:>7.3f}o {vref(target, rs):>10.3f} V   {name}")
    print()
    print("  ^ THESE DIFFER BY 4x. Guessing wrong = half current (weak) or")
    print("    double current (cooked driver). Read the markings first.")
    print()

    # show the damage of guessing wrong
    print("=" * 70)
    print("WHAT GUESSING WRONG ACTUALLY COSTS")
    print("=" * 70)
    print(f"  {'you assume':>11} {'you have':>9} {'Vref set':>9} {'actual I':>9}  result")
    print("  " + "-" * 66)
    for assumed, _ in BOARDS[:1] + BOARDS[2:3]:
        for actual, _ in BOARDS[:1] + BOARDS[2:3]:
            if assumed == actual:
                continue
            v = vref(target, assumed)
            got = imax_from_vref(v, actual)
            ratio = got / target
            if ratio > 1.5:
                verdict = f"{ratio:.1f}x OVER — driver overheats//cooks"
            elif ratio < 0.7:
                verdict = f"{ratio:.1f}x under — skips steps, buzzes, crawls"
            else:
                verdict = "ok-ish"
            print(f"  {assumed:>10.3f}o {actual:>8.3f}o {v:>8.3f}V {got:>8.2f}A  {verdict}")
    print()
    print("  Run again with --rsense <your value> for the single number to dial in.")


if __name__ == "__main__":
    main()
