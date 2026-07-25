/*
 * CNC Shield V3 — dead-simple 4-motor test. No ramp, no microstepping.
 * Runs at 2000 us/step = the SAME speed that worked on your breadboard,
 * just on the shield's 4 sockets. If it worked there and jitters here, the
 * code is NOT the cause — it's the shield wiring.
 *
 * Pins verified against the standard CNC Shield V3 pinout:
 *   X = D2/D5   Y = D3/D6   Z = D4/D7   A = D12/D13   EN = D8 (LOW = on)
 */
const int EN      = 8;
const int STEP[4] = { 2, 3, 4, 12 };
const int DIR[4]  = { 5, 6, 7, 13 };

void setup() {
  pinMode(EN, OUTPUT);
  digitalWrite(EN, LOW);
  for (int i = 0; i < 4; i++) {
    pinMode(STEP[i], OUTPUT);
    pinMode(DIR[i], OUTPUT);
    digitalWrite(DIR[i], HIGH);
    digitalWrite(STEP[i], LOW);
  }
}

void loop() {
  for (int i = 0; i < 4; i++) digitalWrite(STEP[i], HIGH);
  delayMicroseconds(3);
  for (int i = 0; i < 4; i++) digitalWrite(STEP[i], LOW);
  delayMicroseconds(2000);          // same slow speed that worked on breadboard
}
