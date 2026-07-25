/*
 * A4988 single motor — same wiring as the YouTube code (just DIR=D2, STEP=D3),
 * but FASTER. No extra wires, no microstepping pins.
 *
 * It starts at the slow speed that already worked for you (2000 us) and RAMPS
 * up to a faster cruise. The ramp is the trick: a stepper can't start fast, but
 * it can start slow and speed up.
 *
 * TUNING: dMin = top speed. Lower = faster. If it stalls/screams at the top,
 * raise dMin back up until it's smooth.
 *
 * QUIETER needs microstepping, which needs 3 more wires: jumper the A4988's
 * MS1, MS2, MS3 all to +5V (= 1/16 step, much quieter). Then lower dMin further
 * for the same visible speed. Optional — the below works without it.
 */
const int dirPin  = 2;
const int stepPin = 3;

const int dStart = 2000;   // the slow speed that already worked (gentle launch)
const int dMin   = 600;    // top speed. smaller = faster. raise if it stalls.
int d;

void setup() {
  pinMode(dirPin, OUTPUT);
  pinMode(stepPin, OUTPUT);
  digitalWrite(dirPin, HIGH);
  d = dStart;
}

void loop() {
  digitalWrite(stepPin, HIGH);
  delayMicroseconds(3);
  digitalWrite(stepPin, LOW);
  delayMicroseconds(d);
  if (d > dMin) d--;         // accelerate from 2000 down to dMin
}
