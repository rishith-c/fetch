# FETCH — verified parts reference

Every number here is from a manufacturer datasheet or the chip/board spec, with
sources at the bottom. Cross-checked July 2026.

## Motor — JK42HS40-1704-13A (NEMA 17)
| Spec | Value |
|---|---|
| Step angle | 1.8° → **200 steps/rev** |
| Phases / wires | 2 phase, 4 wire (bipolar) |
| Rated current | **1.7 A / phase** (peak) |
| Rated voltage | 2.55 V |
| Phase resistance | 1.5 Ω ±10% |
| Phase inductance | 2.3 mH ±20% |
| Holding torque | **0.42 N·m** (4.2 kg·cm) |
| Body | 42 × 42 × ~40 mm |
| Weight | ~0.24–0.28 kg |
| Shaft | 5 mm, D-cut |

### Wire → coil map (THE thing that stops the vibration)
| Wire | Function | Coil | Goes to driver pair |
|---|---|---|---|
| **Black** | A+ | **Coil A** | 1A / 1B |
| **Green** | A− | **Coil A** | 1A / 1B |
| **Red** | B+ | **Coil B** | 2A / 2B |
| **Blue** | B− | **Coil B** | 2A / 2B |

Each driver pair gets **both wires of one coil**. Split a coil (e.g. Black+Red
in one pair) → motor vibrates, won't turn. **Verify with a multimeter:** the two
wires reading ~1.5 Ω together are one coil (colors vary between batches).

## Driver — A4988, R100 sense resistors
| Spec | Value |
|---|---|
| Sense resistor (your board) | **R100 = 0.100 Ω** |
| **Vref target** | **1.02 V** ( = 1.275 A = 75% of 1.7 A ) |
| Formula | Vref = I × 8 × Rsense = 1.275 × 8 × 0.100 |
| VMOT range | 8–35 V (11.1 V pack is fine) |
| Current limit | ~1 A bare, ~1.5 A with heatsink, 2 A with airflow |
| Microstep (1/4) | **MS2 jumper ONLY** (MS1 off, MS3 off) — same on all four. MS1+MS2 = 1/8, not 1/4 |
| Motor pins | 1B 1A 2B 2A → coil A = 1A/1B, coil B = 2A/2B |

If your board were R050 the target would be 0.51 V; R200 → 2.04 V. **Yours is
R100 → 1.02 V.**

## Shield — CNC Shield V3
| Socket | STEP | DIR | Wheel |
|---|---|---|---|
| X | D2 | D5 | front-left |
| Y | D3 | D6 | front-right |
| Z | D4 | D7 | rear-left |
| A | D12 | D13 | rear-right (set bottom-left jumpers to D12/D13) |

- Enable: **D8** (LOW = drivers on)
- Motor power terminal silkscreen says 12–36 V; the A4988 chip itself is 8–35 V.

## Board — Arduino Uno R4
| Spec | Value |
|---|---|
| MCU | Renesas RA4M1, 48 MHz, 32-bit |
| Flash / RAM | 256 KB / 32 KB |
| Logic level | 5 V |

## Golden rules (each one kills an A4988)
1. **Never connect/disconnect a motor with power on** — the coil spike blows the driver.
2. **Set Vref with the motor disconnected**, USB power only, 12 V off.
3. **Check driver orientation** before powering — backwards = instant death.

## Sources
- Motor datasheet — [JKONGMOTOR JK42HS40-1704-13A](https://www.jkongmotor.com/nema-17-jk42hs40-1704-13a-hybrid-stepper-motor.html)
- Motor specs — [Abra Electronics JK42HS40-1704](https://abra-electronics.com/electromechanical/motors/stepper-motors/nema-17/jk42hs40-1704.html), [anodas.lt](https://www.anodas.lt/en/stepper-motor-jk42hs40-1704-200-steps-rev-2-8v-1-7a-0-4nm)
- A4988 + CNC Shield pinout — [Envistia Mall CNC Shield V3 guide](https://envistiamall.com/blogs/learn/cnc-expansion-shield-v3-for-a4988-and-drv8825-stepper-motor-drivers-user-guide), [makerguides A4988 tutorial](https://www.makerguides.com/a4988-stepper-motor-driver-arduino-tutorial/)
