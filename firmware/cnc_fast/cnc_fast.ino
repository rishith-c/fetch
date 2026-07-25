/*
 * CNC Shield V3 — all 4 motors, FAST. UNO R4 + 4x A4988 (R100, Vref 1.02V).
 *
 * A stepper can't start fast (it stalls). So this launches slow and RAMPS up
 * to a fast cruise. To go faster: lower dMin. If it stalls/screams at the top,
 * raise dMin back up a bit. That number IS your top speed.
 *
 * Sockets: X=D2/D5  Y=D3/D6  Z=D4/D7  A=D12/D13   EN=D8 (LOW=on)
 * (No microstep jumpers = full step = fastest RPM per pulse, but loud.)
 */
const int EN         = 8;
const int STEP[4]    = {  2,  3,  4, 12 };
const int DIR_PIN[4] = {  5,  6,  7, 13 };
const bool DIR[4]    = { HIGH, HIGH, HIGH, HIGH };   // flip any to LOW to reverse

const int dStart = 2500;   // gentle launch, us between steps (must start slow)
const int dMin   = 400;    // TOP SPEED. lower = faster. raise if it stalls.
const int accel  = 1;      // us shaved per step (bigger = snappier ramp)
int d;

void setup() {
  pinMode(EN, OUTPUT);
  digitalWrite(EN, LOW);
  for (int i = 0; i < 4; i++) {
    pinMode(STEP[i], OUTPUT);
    pinMode(DIR_PIN[i], OUTPUT);
    digitalWrite(DIR_PIN[i], DIR[i]);
    digitalWrite(STEP[i], LOW);
  }
  d = dStart;
}

void loop() {
  for (int i = 0; i < 4; i++) digitalWrite(STEP[i], HIGH);
  delayMicroseconds(3);
  for (int i = 0; i < 4; i++) digitalWrite(STEP[i], LOW);
  delayMicroseconds(d);
  if (d > dMin) d -= accel;        // accelerate to top speed, then hold
}
