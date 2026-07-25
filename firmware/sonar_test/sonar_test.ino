/*
 * SONAR TEST — sensors only. No motors, no servo, no scheduler.
 * Purpose: find out why the HC-SR04s read zero. Prints far more than
 * fetch_final does so each failure mode looks different.
 *
 * Wiring under test:
 *   TRIG (all five, shared) -> D9
 *   ECHO f=D10  lf=A1  rf=A2  lr=A3  rr=A4
 *
 * Differences from fetch_final, deliberately, to rule things out:
 *   - 25 ms timeout (~4 m) instead of 6 ms (~1 m). If a sensor only reports
 *     here, the target was simply further than 1 m.
 *   - 80 ms between TRIG pulses. HC-SR04 needs >=60 ms per measurement cycle;
 *     the shared trigger in fetch_final fires EVERY sensor on every tick, so
 *     at 30 ms they were being re-triggered mid-measurement.
 *   - plain INPUT, not INPUT_PULLDOWN, in case the pulldown fights the echo.
 *   - prints the IDLE level of each echo pin. A healthy idle echo is LOW.
 *     Stuck HIGH  = miswired / sensor held in reset / no common ground.
 *     Always LOW + no pulse = TRIG not arriving, or no power at the sensor.
 */
const int TRIG = 9;
const int ECHO[5] = { 10, A1, A2, A3, A4 };
const char* NAME[5] = { "f ", "lf", "rf", "lr", "rr" };

void setup() {
  Serial.begin(115200);
  pinMode(TRIG, OUTPUT);
  digitalWrite(TRIG, LOW);
  for (int i = 0; i < 5; i++) pinMode(ECHO[i], INPUT);
  delay(300);
  Serial.println();
  Serial.println("SONAR TEST — 25ms timeout (~4m), 80ms cycle, plain INPUT");
  Serial.println("idle= level before the ping (want LOW)   us= echo width   cm= distance");
}

// Some CNC shields have RC filter caps on the endstop pins, which swallow a
// 10 us pulse entirely. HC-SR04 accepts anything >=10 us, so a long pulse is
// harmless and proves whether the trigger is being filtered.
int trigUs = 10;

void loop() {
  trigUs = (trigUs == 10) ? 200 : 10;      // alternate short / long each pass
  Serial.print("=== TRIG pulse "); Serial.print(trigUs); Serial.println(" us ===");

  // idle levels first: this is the wiring check
  Serial.print("idle ");
  for (int i = 0; i < 5; i++) {
    Serial.print(NAME[i]); Serial.print('=');
    Serial.print(digitalRead(ECHO[i]) ? "HIGH " : "low  ");
  }
  Serial.println();

  for (int i = 0; i < 5; i++) {
    digitalWrite(TRIG, LOW);  delayMicroseconds(4);
    digitalWrite(TRIG, HIGH); delayMicroseconds(trigUs);
    digitalWrite(TRIG, LOW);
    unsigned long us = pulseIn(ECHO[i], HIGH, 25000UL);
    Serial.print("  "); Serial.print(NAME[i]);
    Serial.print("  us="); Serial.print(us);
    Serial.print("  cm=");
    if (us == 0) Serial.println("-- (no echo)");
    else Serial.println(us / 58);
    delay(80);                      // >=60 ms per HC-SR04 measurement cycle
  }
  // 3 slow blinks so the trigger line can be checked with a multimeter:
  // probe the TRIG pin AT A SENSOR - it should swing between 0 V and ~5 V.
  Serial.println("TRIG blink x3 (meter it at the sensor's TRIG pin)");
  for (int b = 0; b < 3; b++) {
    digitalWrite(TRIG, HIGH); delay(400);
    digitalWrite(TRIG, LOW);  delay(400);
  }
  Serial.println();
}
