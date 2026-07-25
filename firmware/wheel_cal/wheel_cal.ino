/*
 * WHEEL CALIBRATION — spins ONE wheel at a time, slowly, in this order:
 *
 *     1st = X   2nd = Y   3rd = Z   4th = A     (3s each, 2s pause, repeats)
 *
 * Put the robot on the floor (or hold it up). For EACH spin write down:
 *   1) WHICH corner moved:  front-left / front-right / back-left / back-right
 *      (from the ROBOT's view — as if you're driving it)
 *   2) Which way it rolled: would it push the robot FORWARD or BACKWARD?
 *
 * Four observations = the complete truth. No more guessing.
 */
const int EN = 8;
const int STEP[4] = { 2, 3, 4, 12 };    // X, Y, Z, A
const int DIRP[4] = { 5, A2, 7, 13 };   // Y dir on A2

void setup() {
  pinMode(EN, OUTPUT); digitalWrite(EN, LOW);
  for (int i = 0; i < 4; i++) {
    pinMode(STEP[i], OUTPUT); pinMode(DIRP[i], OUTPUT);
    digitalWrite(DIRP[i], HIGH);        // raw HIGH on every dir — we OBSERVE what that means
    digitalWrite(STEP[i], LOW);
  }
  delay(3000);
}

void spinOne(int i) {
  unsigned long t0 = millis();
  while (millis() - t0 < 3000) {        // spin this one wheel for 3 s
    digitalWrite(STEP[i], HIGH); delayMicroseconds(4);
    digitalWrite(STEP[i], LOW);  delayMicroseconds(3000);
    yield();
  }
  delay(2000);                          // pause so you can note it down
}

void loop() {
  for (int i = 0; i < 4; i++) spinOne(i);   // X, Y, Z, A
  delay(4000);                              // long gap, then the cycle repeats
}
