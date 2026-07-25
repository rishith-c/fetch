/*
 * Single-motor test — spins ONLY the socket you pick.
 * UNO R4 + CNC Shield V3 + A4988 (R100, Vref 1.02 V) + JK42HS40.
 *
 * TEST = the socket your test motor is plugged into:
 *     0 = X (D2/D5)   1 = Y (D3/D6)   2 = Z (D4/D7)   3 = A (D12/D13)
 *
 * MODE 0 = ~2 steps/sec (watch each click)
 * MODE 1 = ~125 steps/sec (smooth continuous — the real "does it work" test)
 *
 * POWER:
 *   - Uno: USB (that's its logic power, separate from the motor supply)
 *   - Motors: bench PSU -> shield's motor screw terminal.  12 V, ~1.5 A limit.
 *   - Only ONE motor needs to be plugged in for this test.
 *   - NEVER connect/disconnect the motor with power on.
 */
#define TEST 0        // <-- set to the socket the motor-under-test is in
#define MODE 1

const int EN      = 8;
const int STEP[4] = { 2, 3, 4, 12 };
const int DIR[4]  = { 5, 6, 7, 13 };

void setup() {
  pinMode(EN, OUTPUT);
  digitalWrite(EN, LOW);                 // drivers on
  pinMode(STEP[TEST], OUTPUT);
  pinMode(DIR[TEST], OUTPUT);
  digitalWrite(DIR[TEST], HIGH);         // one direction
  digitalWrite(STEP[TEST], LOW);
}

void loop() {
  digitalWrite(STEP[TEST], HIGH);
  delayMicroseconds(4);
  digitalWrite(STEP[TEST], LOW);
#if MODE == 0
  delay(500);                            // ~2 steps/sec
#else
  delayMicroseconds(8000);               // ~125 steps/sec
#endif
}
