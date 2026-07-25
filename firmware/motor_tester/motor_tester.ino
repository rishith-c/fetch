/*
 * SERIAL MOTOR TESTER — upload ONCE, then drive it from the Serial Monitor.
 * No more re-uploading per motor.
 *
 *   Open Serial Monitor at 115200, then type:
 *     x  y  z  a   = spin that ONE motor (slowly)
 *     s            = stop
 *     d            = flip direction of the spinning motor
 *
 * Hold the robot UP (wheels off the ground). For each motor report:
 *   which corner wheel it is + spins clean or vibrates + rolls fwd/back.
 */
const int EN = 8;
const int STEP[4] = { 2, 3, 4, 12 };    // X, Y, Z, A
const int DIRP[4] = { 5, A2, 7, 13 };   // Y dir on A2
const char* NAME[4] = { "X", "Y", "Z", "A" };

int  active  = -1;      // which motor is spinning (-1 = none)
bool dirHigh = true;

void setup() {
  Serial.begin(115200);
  pinMode(EN, OUTPUT); digitalWrite(EN, LOW);
  for (int i = 0; i < 4; i++) {
    pinMode(STEP[i], OUTPUT); pinMode(DIRP[i], OUTPUT);
    digitalWrite(DIRP[i], HIGH); digitalWrite(STEP[i], LOW);
  }
  Serial.println("READY. type: x y z a = spin | s = stop | d = flip direction");
}

void loop() {
  if (Serial.available()) {
    char c = tolower(Serial.read());
    int pick = -2;
    if      (c == 'x') pick = 0;
    else if (c == 'y') pick = 1;
    else if (c == 'z') pick = 2;
    else if (c == 'a') pick = 3;
    else if (c == 's') pick = -1;

    if (pick >= -1) {
      active = pick;
      if (active >= 0) {
        digitalWrite(DIRP[active], dirHigh);
        Serial.print("spinning "); Serial.print(NAME[active]);
        Serial.println(dirHigh ? "  (dir HIGH)" : "  (dir LOW)");
      } else Serial.println("stopped");
    } else if (c == 'd') {
      dirHigh = !dirHigh;
      if (active >= 0) digitalWrite(DIRP[active], dirHigh);
      Serial.println(dirHigh ? "direction: HIGH" : "direction: LOW");
    }
  }

  if (active >= 0) {
    digitalWrite(STEP[active], HIGH); delayMicroseconds(4);
    digitalWrite(STEP[active], LOW);  delayMicroseconds(3000);
  }
  yield();
}
