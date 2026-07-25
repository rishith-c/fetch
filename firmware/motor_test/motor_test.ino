/*
 * FETCH — motor bench test.  Arduino Uno + CNC Shield V3 + 4x A4988.
 *
 * Spins all four motors slowly in one direction, forever. This is a HARDWARE
 * test, not the real firmware — it just proves each motor is wired right and
 * the Vref is set right, before you hook up the Pi.
 *
 * The step rate here is deliberately SLOW (~330 steps/sec). At this speed a
 * correctly-wired motor turns smoothly. So:
 *    - turns smoothly  -> that motor + driver + Vref are GOOD
 *    - screams/vibrates and won't turn -> that motor's COIL PAIR is wired
 *      wrong (1A/1B and 2A/2B must each get BOTH wires of ONE coil).
 *      It is NOT a speed problem at this rate.
 *
 * BEFORE UPLOADING:
 *    - motors plugged in with POWER OFF
 *    - 12V motor supply ON and USB connected
 *    - Vref already set on all four drivers
 *
 * To test ONE motor at a time (to find which is bad), set ONLY_ONE below to
 * 0/1/2/3  (X/Y/Z/A).  -1 spins all four.
 */

const int EN      = 8;                    // enable, LOW = drivers on
const int STEP[4] = { 2,  3,  4, 12 };    // X, Y, Z, A   (CNC Shield V3)
const int DIR[4]  = { 5,  6,  7, 13 };
const char* NAME[4] = { "X", "Y", "Z", "A" };

const int  ONLY_ONE   = -1;               // -1 = all; 0..3 = just that one
const int  STEP_US    = 3;                // pulse width
const int  GAP_US     = 3000;             // ~330 steps/sec — slow + smooth

void setup() {
  Serial.begin(115200);
  pinMode(EN, OUTPUT);
  digitalWrite(EN, LOW);                  // drivers ON
  for (int i = 0; i < 4; i++) {
    pinMode(STEP[i], OUTPUT);
    pinMode(DIR[i], OUTPUT);
    digitalWrite(DIR[i], HIGH);           // all same direction
    digitalWrite(STEP[i], LOW);
  }
  Serial.println(ONLY_ONE < 0 ? "spinning ALL 4" : NAME[ONLY_ONE]);
}

void loop() {
  for (int i = 0; i < 4; i++) {
    if (ONLY_ONE >= 0 && i != ONLY_ONE) continue;
    digitalWrite(STEP[i], HIGH);
  }
  delayMicroseconds(STEP_US);
  for (int i = 0; i < 4; i++) digitalWrite(STEP[i], LOW);
  delayMicroseconds(GAP_US);
}
