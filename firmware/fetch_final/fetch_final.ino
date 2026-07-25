/*
 * FETCH FINAL — everything: 4 steppers + 5 sonars + MG90S tilt servo + Pi.
 *
 * MOTORS: identical to fetch_steppers (the user's proven wiring/kinematics).
 *   FL = X (2,5)  FR = Y (3,6)  RL = Z (4,7) POL -1  RR = A (12,A0)  EN 8
 *   Mix: FL = fwd+side  FR = fwd-side  RL = fwd-side  RR = fwd+side
 *   NOTE the +side on FL. Flipping it sends every diagonal down the wrong axis.
 *
 * SENSORS: A0 is RR's direction pin, so the echoes route around it and use
 *   A2 (Resume) instead — A2 is free now that Y-DIR lives on D6.
 *     TRIG (all five, one shared wire) -> D9   (X+ endstop)
 *     ECHO front       D10 (Y+ endstop)   ECHO left-front  A1 (Hold)
 *     ECHO right-front A2  (Resume)       ECHO left-rear   A3 (CoolEn)
 *     ECHO right-rear  A4  (SDA)
 * SERVO: signal D11 (Z+ endstop). Power from the BUCK at 5 V, never the Uno.
 * SPARE: D13, A5, D0, D1
 *
 * SERIAL 115200
 *   v <vx> <vy> <w>   -100..100 each   vx fwd, vy right, w clockwise
 *   f b l r q e s     manual keys       + -   speed step
 *   m <corner> <spd>  one motor: 0=FL 1=FR 2=RL 3=RR
 *   t <0-180>         camera tilt
 *   c                 crab circle (~30 cm)      ?  report state
 *   OUT: "us f=52 lf=110 rf=0 lr=88 rr=200"  cm, 0 = no echo, ~7 Hz
 *
 * SAFETY, both on the Uno so neither depends on WiFi:
 *   - v-mode stops if the Pi goes quiet 500 ms
 *   - forward motion refused under 25 cm front clearance
 */
#include <AccelStepper.h>
#include <Servo.h>
#include <math.h>

AccelStepper FL(AccelStepper::DRIVER, 2, 5);    // X  top-left
AccelStepper FR(AccelStepper::DRIVER, 3, 6);    // Y  top-right
AccelStepper RL(AccelStepper::DRIVER, 4, 7);    // Z  bottom-left
AccelStepper RR(AccelStepper::DRIVER, 12, A0);  // A  bottom-right (A0 = Abort)
AccelStepper* M[4] = { &FL, &FR, &RL, &RR };
const float POL[4] = { +1, +1, -1, +1 };        // RL inverted in hardware

const int ENABLE_PIN = 8;
const float STEPS_PER_REV = 200.0;
const float WHEEL_CIRC_M  = 0.0800 * M_PI;
const float MAX_MS        = 0.30;
const float MAX_SPS       = MAX_MS * (STEPS_PER_REV / WHEEL_CIRC_M);

const float CIRCLE_DIAMETER_M = 0.30;
const float SECONDS_PER_LAP   = 4.0;

const int TRIG = 9;
const int ECHO[5] = { 10, A1, A2, A3, A4 };     // f, lf, rf, lr, rr
const char* USNAME[5] = { "f", "lf", "rf", "lr", "rr" };
const int FRONT = 0, VETO_CM = 25;
int usCM[5] = { 0, 0, 0, 0, 0 };
int usIdx = 0;

const int SERVO_PIN = 11;
Servo tilt;

float curVX = 0, curVY = 0, curW = 0;
int speedPct = 60;
bool vMode = false;
unsigned long lastV = 0, lastPing = 0, lastReport = 0;
char line[40];
byte lineLen = 0;

void setVel(float vx, float vy, float w) {
  if (vx > 0 && usCM[FRONT] > 0 && usCM[FRONT] < VETO_CM) vx = 0;   // veto
  curVX = vx; curVY = vy; curW = w;
  float s[4];
  s[0] = vx + vy + w;      // FL
  s[1] = vx - vy - w;      // FR
  s[2] = vx - vy + w;      // RL
  s[3] = vx + vy - w;      // RR
  float mx = 0;
  for (int i = 0; i < 4; i++) mx = max(mx, fabs(s[i]));
  if (mx > 1.0) for (int i = 0; i < 4; i++) s[i] /= mx;
  for (int i = 0; i < 4; i++) M[i]->setSpeed(POL[i] * s[i] * MAX_SPS);
}

void runAll() { for (int i = 0; i < 4; i++) M[i]->runSpeed(); }

void pingOne(int i) {
  digitalWrite(TRIG, LOW);  delayMicroseconds(4);
  digitalWrite(TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  unsigned long us = pulseIn(ECHO[i], HIGH, 6000UL);   // 6 ms cap ~ 1 m
  usCM[i] = us ? (int)(us / 58) : 0;
  if (i == FRONT && curVX > 0 && usCM[FRONT] > 0 && usCM[FRONT] < VETO_CM)
    setVel(0, curVY, curW);
}

void crabCircle() {
  float V   = (M_PI * CIRCLE_DIAMETER_M) / SECONDS_PER_LAP;
  float amp = min(1.0f, (float)(V / MAX_MS));
  unsigned long t0 = millis();
  while ((millis() - t0) / 1000.0 < SECONDS_PER_LAP) {
    float ang = 2.0 * M_PI * ((millis() - t0) / 1000.0) / SECONDS_PER_LAP;
    setVel(amp * sin(ang), amp * cos(ang), 0);
    unsigned long slice = millis();
    while (millis() - slice < 12) { runAll(); yield(); }
    if (Serial.available()) { Serial.read(); break; }
  }
  setVel(0, 0, 0);
}

void handleLine() {
  line[lineLen] = 0;
  char c = line[0];
  if (c == 'v') {
    // strtol, NOT sscanf: newlib-nano here has no %f in scanf.
    char *p = line + 1;
    long v[3] = { 0, 0, 0 };
    for (int i = 0; i < 3; i++) v[i] = strtol(p, &p, 10);
    setVel(v[0] / 100.0f, v[1] / 100.0f, v[2] / 100.0f);
    vMode = true; lastV = millis();
  } else if (c == 't') {
    tilt.write(constrain((int)strtol(line + 1, NULL, 10), 0, 180));
  } else if (c == 'm') {
    char *p = line + 1;
    long idx = strtol(p, &p, 10);
    long spd = strtol(p, &p, 10);
    for (int i = 0; i < 4; i++) M[i]->setSpeed(0);
    if (idx >= 0 && idx < 4) M[idx]->setSpeed(POL[idx] * (spd / 100.0f) * MAX_SPS);
    curVX = curVY = curW = 0;
    vMode = false;
  } else {
    float s = speedPct / 100.0f; vMode = false;
    if      (c == 'f') setVel( s, 0, 0);
    else if (c == 'b') setVel(-s, 0, 0);
    else if (c == 'l') setVel(0, -s, 0);
    else if (c == 'r') setVel(0,  s, 0);
    else if (c == 'q') setVel(0, 0, -s);
    else if (c == 'e') setVel(0, 0,  s);
    else if (c == 's') setVel(0, 0, 0);
    else if (c == 'c') crabCircle();
    else if (c == '?') {
      Serial.print("vx="); Serial.print(curVX);
      Serial.print(" vy="); Serial.print(curVY);
      Serial.print(" w=");  Serial.print(curW);
      Serial.print(" spd="); Serial.println(speedPct);
    }
    else if (c == '+' || c == '-')
      speedPct = constrain(speedPct + (c == '+' ? 10 : -10), 20, 100);
  }
  lineLen = 0;
}

void setup() {
  Serial.begin(115200);
  pinMode(ENABLE_PIN, OUTPUT); digitalWrite(ENABLE_PIN, LOW);
  float top = MAX_SPS * 1.6;
  for (int i = 0; i < 4; i++) { M[i]->setMaxSpeed(top); M[i]->setSpeed(0); }
  pinMode(TRIG, OUTPUT); digitalWrite(TRIG, LOW);
  for (int i = 0; i < 5; i++) pinMode(ECHO[i], INPUT);
  tilt.attach(SERVO_PIN); tilt.write(90);
  Serial.println("FETCH FINAL READY");
}

void loop() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') { if (lineLen) handleLine(); }
    else if (lineLen < sizeof(line) - 1) {
      line[lineLen++] = ch;
      if (lineLen == 1 && strchr("fblrqsec+-?", ch)) handleLine();
    }
  }

  bool moving = (fabs(curVX) + fabs(curVY) + fabs(curW)) > 0.05;
  if (millis() - lastPing >= (unsigned long)(moving ? 150 : 30)) {
    lastPing = millis();
    pingOne(usIdx);
    usIdx = (usIdx + 1) % 5;
  }

  if (millis() - lastReport >= 140) {
    lastReport = millis();
    Serial.print("us");
    for (int i = 0; i < 5; i++) {
      Serial.print(' '); Serial.print(USNAME[i]);
      Serial.print('='); Serial.print(usCM[i]);
    }
    Serial.println();
  }

  if (vMode && millis() - lastV > 500) { setVel(0, 0, 0); vMode = false; }

  runAll();
  yield();
}
