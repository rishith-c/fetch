/*
 * TT-KIT MECANUM DRIVER (L298N version) — the real drive firmware for the
 * new chassis. Same setVel() kinematics as the stepper build, but PWM.
 *
 * Serial control at 115200 (works from Serial Monitor AND from the Pi relay):
 *   f b l r   = forward / back / strafe-left / strafe-right
 *   q e       = spin left / spin right
 *   s         = stop
 *   + / -     = speed up / down
 *   v vx vy w = velocity command, each -100..100  (e.g. "v 60 0 0")
 *               -> this is the line fetch_relay.py sends
 * Watchdog: if no 'v' command for 500 ms while in v-mode, motors stop.
 *
 * WIRING (Freenove Uno R4 -> 2x L298N), same map as tt_motor_tester:
 *   M1: EN=D5  IN1=D2  IN2=D4      M3: EN=D9  IN1=D12 IN2=D13
 *   M2: EN=D6  IN1=D7  IN2=D8      M4: EN=D10 IN1=A0  IN2=A1
 *   ENA/ENB jumper caps removed; GND jumper each board -> Uno GND.
 *
 * CALIBRATION DAY-OF (from tt_motor_tester observations):
 *   1) set CORNER[] so index 0..3 = which M# sits at FL, FR, RL, RR
 *   2) set POL[] +1/-1 per motor so "f" makes every wheel roll forward
 */
const int EN[4]  = { 5, 6, 9, 10 };
const int IN1[4] = { 2, 7, 12, A0 };
const int IN2[4] = { 4, 8, 13, A1 };

// CORNER[FL,FR,RL,RR] = motor index (0-3) at that corner  — EDIT AFTER TESTING
const int CORNER[4] = { 0, 1, 2, 3 };
// POL[motor] = +1 or -1 so positive = robot-forward              — EDIT AFTER TESTING
const int POL[4] = { +1, +1, +1, +1 };

// Buck at 7.5 V makes 100% duty safe (motors see ~5.7 V), so no PWM cap needed.
int speedPct = 60;                    // f/b/l/r command speed, percent

unsigned long lastV = 0;
bool vMode = false;

void motorOut(int m, int pwm) {       // pwm -255..255, sign = direction
  pwm *= POL[m];
  bool forward = pwm >= 0;
  digitalWrite(IN1[m], forward ? HIGH : LOW);
  digitalWrite(IN2[m], forward ? LOW  : HIGH);
  analogWrite(EN[m], constrain(abs(pwm), 0, 255));
}

// Mecanum kinematics — identical math to the stepper build.
// vx = fwd+, vy = strafe right+, w = spin CW+, each -100..100
void setVel(float vx, float vy, float w) {
  float fl = vx - vy - w;
  float fr = vx + vy + w;
  float rl = vx + vy - w;
  float rr = vx - vy + w;
  float mx = max(max(abs(fl), abs(fr)), max(abs(rl), abs(rr)));
  if (mx > 100) { fl *= 100/mx; fr *= 100/mx; rl *= 100/mx; rr *= 100/mx; }
  motorOut(CORNER[0], fl * 2.55);
  motorOut(CORNER[1], fr * 2.55);
  motorOut(CORNER[2], rl * 2.55);
  motorOut(CORNER[3], rr * 2.55);
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50);      // parseFloat must never block the control loop
  for (int i = 0; i < 4; i++) {
    pinMode(EN[i], OUTPUT); pinMode(IN1[i], OUTPUT); pinMode(IN2[i], OUTPUT);
  }
  setVel(0, 0, 0);
  Serial.println("TT MECANUM READY. f b l r q e s +/- | v vx vy w");
}

void loop() {
  if (Serial.available()) {
    char c = Serial.peek();
    if (c == 'v') {                          // "v vx vy w" line from the Pi
      Serial.read();
      float vx = Serial.parseFloat();
      float vy = Serial.parseFloat();
      float w  = Serial.parseFloat();
      while (Serial.available() && Serial.read() != '\n') {}
      setVel(vx, vy, w);
      vMode = true; lastV = millis();
    } else {
      Serial.read();
      float s = speedPct;
      vMode = false;
      if      (c == 'f') setVel( s, 0, 0);
      else if (c == 'b') setVel(-s, 0, 0);
      else if (c == 'l') setVel(0, -s, 0);
      else if (c == 'r') setVel(0,  s, 0);
      else if (c == 'q') setVel(0, 0, -s);
      else if (c == 'e') setVel(0, 0,  s);
      else if (c == 's') setVel(0, 0, 0);
      else if (c == '+' || c == '-') {
        speedPct = constrain(speedPct + (c == '+' ? 10 : -10), 20, 100);
        Serial.print("speed "); Serial.print(speedPct); Serial.println("%");
      }
    }
  }
  if (vMode && millis() - lastV > 500) {     // watchdog: Pi went quiet -> stop
    setVel(0, 0, 0); vMode = false;
  }
  yield();
}
