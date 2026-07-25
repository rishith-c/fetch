/*
 * PART 2 — ALL 5 HC-SR04 on the Arduino CNC Shield V3.
 * Prints each sensor's distance by name in the Serial Monitor (115200), e.g.:
 *     front=42 L-front=110 L-rear=999 R-rear=88 R-front=205
 * (999 = nothing in range / not wired.) This same line is what the heatmap
 * GUI reads.
 *
 * PIN MAP  (US3 echo is on A5, NOT A2 — A2 is the Y-DIR jumper):
 *   US1 front        TRIG D9   ECHO D10
 *   US2 left-front   TRIG D11  ECHO A0
 *   US3 left-rear    TRIG A1   ECHO A5
 *   US4 right-rear   TRIG A3   ECHO D0
 *   US5 right-front  TRIG D1   ECHO A4
 * Every sensor also: VCC -> 5V rail, GND -> GND.
 */
const int N = 5;
const int TRIG[N] = {  9, 11, A1, A3,  1 };
const int ECHO[N] = { 10, A0, A5,  0, A4 };
const char* NAME[N] = { "front", "L-front", "L-rear", "R-rear", "R-front" };

long readCM(int t, int e) {
  digitalWrite(t, LOW);  delayMicroseconds(2);
  digitalWrite(t, HIGH); delayMicroseconds(10);
  digitalWrite(t, LOW);
  long dur = pulseIn(e, HIGH, 25000);
  return (dur == 0) ? 999 : dur / 58;
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < N; i++) {
    pinMode(TRIG[i], OUTPUT);
    pinMode(ECHO[i], INPUT);
  }
}

void loop() {
  for (int i = 0; i < N; i++) {
    long cm = readCM(TRIG[i], ECHO[i]);
    Serial.print(NAME[i]); Serial.print("="); Serial.print(cm);
    if (i < N - 1) Serial.print(" ");
    delay(25);                     // spacing so echoes don't cross-talk
  }
  Serial.println();
  delay(120);
}
