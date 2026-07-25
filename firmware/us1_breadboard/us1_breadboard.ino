/*
 * PART 1 — SINGLE HC-SR04 on a breadboard to Arduino Uno.
 * Prints the distance to the nearest object in the Serial Monitor.
 *
 * WIRING (HC-SR04 -> breadboard -> Uno):
 *   HC-SR04 VCC  -> Uno 5V
 *   HC-SR04 Trig -> Uno D9
 *   HC-SR04 Echo -> Uno D10
 *   HC-SR04 GND  -> Uno GND
 *
 * Open Serial Monitor at 9600. Move your hand toward the sensor — the number
 * drops. That's the distance to the nearest thing in front of it.
 */
const int trigPin = 9;
const int echoPin = 10;

void setup() {
  Serial.begin(9600);
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
}

void loop() {
  // send a 10us pulse
  digitalWrite(trigPin, LOW);  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH); delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  // time the echo, convert to cm
  long duration = pulseIn(echoPin, HIGH, 25000);   // 25ms timeout (~4m)
  if (duration == 0) {
    Serial.println("Distance: -- (out of range)");
  } else {
    long cm = duration / 58;
    Serial.print("Distance: ");
    Serial.print(cm);
    Serial.println(" cm");
  }
  delay(200);
}
