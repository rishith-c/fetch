/*
 * SENSOR TEST — reads all 5 HC-SR04 ultrasonics and prints distances.
 * Use this to confirm each sensor is wired right BEFORE the full firmware.
 *
 * Open Serial Monitor at 115200. Wave your hand in front of each sensor and
 * watch its number drop. If one reads 0 or 999 forever, its wiring is wrong.
 *
 * PIN MAP (US3 echo is on A5, not A2 — A2 is taken by the Y-DIR jumper):
 *   US1 front        TRIG D9   ECHO D10
 *   US2 left-front   TRIG D11  ECHO A0
 *   US3 left-rear    TRIG A1   ECHO A5   <-- moved off A2
 *   US4 right-rear   TRIG A3   ECHO D0
 *   US5 right-front  TRIG D1   ECHO A4
 *
 * Each sensor also needs: VCC -> 5V rail, GND -> GND.
 */
const int N = 5;
const int TRIG[N] = {  9, 11, A1, A3,  1 };
const int ECHO[N] = { 10, A0, A5,  0, A4 };
const char* NAME[N] = { "front", "L-front", "L-rear", "R-rear", "R-front" };

long readCM(int t, int e) {
  digitalWrite(t, LOW);  delayMicroseconds(2);
  digitalWrite(t, HIGH); delayMicroseconds(10);
  digitalWrite(t, LOW);
  long dur = pulseIn(e, HIGH, 25000);   // 25ms timeout ~ 4m max
  if (dur == 0) return 999;             // nothing / not wired
  return dur / 58;                      // us -> cm
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < N; i++) {
    pinMode(TRIG[i], OUTPUT);
    pinMode(ECHO[i], INPUT);
  }
  Serial.println("sensor test — wave a hand at each; its number should drop");
}

void loop() {
  for (int i = 0; i < N; i++) {
    long cm = readCM(TRIG[i], ECHO[i]);
    Serial.print(NAME[i]); Serial.print("="); Serial.print(cm); Serial.print("cm  ");
    delay(30);                          // let echoes settle between sensors
  }
  Serial.println();
  delay(200);
}
