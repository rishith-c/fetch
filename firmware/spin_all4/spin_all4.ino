/*
 * FETCH — 4-motor spin + wiring diagnostic.
 * Arduino UNO R4 + CNC Shield V3 + 4x A4988 (R100 sense) + 4x NEMA17.
 *
 * ============================ VERIFIED NUMBERS ============================
 * Motor  JK42HS40-1704-13A (NEMA17):  1.8 deg / 200 steps-rev, 1.7 A/phase,
 *        1.5 ohm, ~2.3 mH, 0.42 N.m holding, D-shaft.        (JKONGMOTOR)
 * Driver A4988, R100 sense resistors  -> Vref = 1.02 V  (= 1.275 A, 75%).
 * WIRING of THIS motor (verified from the JK42HS40-1704 datasheet):
 *        Black (A+) + Green (A-) = COIL A  -> driver pair 1A / 1B
 *        Red   (B+) + Blue  (B-) = COIL B  -> driver pair 2A / 2B
 *   Each driver pair MUST get BOTH wires of ONE coil. If Black & Red end up
 *   in the same pair, the coil is split and the motor just VIBRATES.
 *   Verify with a multimeter: the two wires reading ~1.5 ohm together are one
 *   coil. Colors can vary between batches, so trust the ohm reading.
 * =========================================================================
 *
 * MODE 0 = DIAGNOSTIC: ~2 steps/sec. You SEE each step. A good motor clicks
 *          steadily one way. A miswired one rocks back and forth in place.
 * MODE 1 = RUN: smooth continuous slow spin (~125 steps/sec).
 *
 * ALWAYS connect/disconnect motors with POWER OFF. Hot-plugging kills A4988s.
 */
#define MODE 0

const int EN      = 8;                     // LOW = drivers enabled
const int STEP[4] = { 2,  3,  4, 12 };     // X, Y, Z, A  (CNC Shield V3)
const int DIR[4]  = { 5,  6,  7, 13 };

void setup() {
  pinMode(EN, OUTPUT);
  digitalWrite(EN, LOW);                   // drivers on
  for (int i = 0; i < 4; i++) {
    pinMode(STEP[i], OUTPUT);
    pinMode(DIR[i], OUTPUT);
    digitalWrite(DIR[i], HIGH);            // all one direction
    digitalWrite(STEP[i], LOW);
  }
}

void loop() {
  for (int i = 0; i < 4; i++) digitalWrite(STEP[i], HIGH);
  delayMicroseconds(4);
  for (int i = 0; i < 4; i++) digitalWrite(STEP[i], LOW);
#if MODE == 0
  delay(500);                              // ~2 steps/sec — watch each click
#else
  delayMicroseconds(8000);                 // ~125 steps/sec — smooth run
#endif
}
