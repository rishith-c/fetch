/*
 * TT-KIT MOTOR TESTER (L298N version) — upload ONCE, drive from Serial Monitor.
 * Same idea as the stepper motor_tester, but for the new DC-motor chassis.
 *
 *   Open Serial Monitor at 115200, then type:
 *     1 2 3 4  = spin that ONE motor (half speed)
 *     s        = stop
 *     d        = flip direction of the spinning motor
 *     + / -    = faster / slower
 *
 * Prop the robot up (wheels off the ground). For each motor note:
 *   which corner wheel it is + which way it rolls. That gives us the
 *   corner map + polarity flags for tt_mecanum in one session.
 *
 * WIRING (Freenove Uno R4 -> 2x L298N):
 *   M1: EN=D5  IN1=D2  IN2=D4    (board 1, OUT1/OUT2)
 *   M2: EN=D6  IN1=D7  IN2=D8    (board 1, OUT3/OUT4)
 *   M3: EN=D9  IN1=D12 IN2=D13   (board 2, OUT1/OUT2)
 *   M4: EN=D10 IN1=A0  IN2=A1    (board 2, OUT3/OUT4)
 *   Remove the little ENA/ENB jumper caps so EN pins accept PWM.
 *   GND jumper from EACH L298N to Uno GND. Power: buck 7.5V to both boards.
 */
const int EN[4]  = { 5, 6, 9, 10 };     // PWM pins
const int IN1[4] = { 2, 7, 12, A0 };
const int IN2[4] = { 4, 8, 13, A1 };

int  active  = -1;
bool fwd     = true;
int  speedPWM = 128;                    // half speed to start

void applyMotor(int i, int pwm, bool forward) {
  digitalWrite(IN1[i], forward ? HIGH : LOW);
  digitalWrite(IN2[i], forward ? LOW  : HIGH);
  analogWrite(EN[i], pwm);
}

void stopAll() {
  for (int i = 0; i < 4; i++) { analogWrite(EN[i], 0);
    digitalWrite(IN1[i], LOW); digitalWrite(IN2[i], LOW); }
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) {
    pinMode(EN[i], OUTPUT); pinMode(IN1[i], OUTPUT); pinMode(IN2[i], OUTPUT);
  }
  stopAll();
  Serial.println("TT TESTER READY. 1 2 3 4 = spin | s = stop | d = flip | +/- = speed");
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c >= '1' && c <= '4') {
      stopAll();
      active = c - '1';
      applyMotor(active, speedPWM, fwd);
      Serial.print("spinning M"); Serial.print(active + 1);
      Serial.print(fwd ? " fwd" : " rev");
      Serial.print(" pwm="); Serial.println(speedPWM);
    } else if (c == 's') {
      active = -1; stopAll(); Serial.println("stopped");
    } else if (c == 'd') {
      fwd = !fwd;
      if (active >= 0) applyMotor(active, speedPWM, fwd);
      Serial.println(fwd ? "direction: fwd" : "direction: rev");
    } else if (c == '+' || c == '-') {
      speedPWM = constrain(speedPWM + (c == '+' ? 25 : -25), 50, 255);
      if (active >= 0) applyMotor(active, speedPWM, fwd);
      Serial.print("pwm="); Serial.println(speedPWM);
    }
  }
  yield();
}
