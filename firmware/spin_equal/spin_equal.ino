/*
 * All 4 motors spin EQUALLY — same speed, same direction.
 * UNO R4 + CNC Shield V3. Y-DIR on A2 (jumper; D6 dead).
 *
 * The yield() at the end lets the USB get serviced each loop, so the R4's
 * auto-reset works and you should NOT need the double-tap-reset to upload.
 */
const int EN = 8;
//                     X    Y    Z    A
const int STEP[4] = {  2,   3,   4,  12 };
const int DIRP[4] = {  5,  A2,   7,  13 };        // Y dir on A2
bool      FWD [4] = { HIGH, HIGH, HIGH, HIGH };   // flip any if one spins backward

const int SPEED_US = 1000;    // gap between steps: lower = faster

void setup() {
  pinMode(EN, OUTPUT); digitalWrite(EN, LOW);
  for (int i = 0; i < 4; i++) {
    pinMode(STEP[i], OUTPUT); pinMode(DIRP[i], OUTPUT);
    digitalWrite(DIRP[i], FWD[i]);
  }
}

void loop() {
  for (int i = 0; i < 4; i++) digitalWrite(STEP[i], HIGH);
  delayMicroseconds(4);
  for (int i = 0; i < 4; i++) digitalWrite(STEP[i], LOW);
  delayMicroseconds(SPEED_US);
  yield();                    // service USB -> normal uploads work again
}
