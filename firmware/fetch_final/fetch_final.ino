/*
 * FETCH FINAL — 4 steppers + 3 front sonars + fixed camera + Pi.
 *
 * MOTORS: identical to fetch_steppers (the user's proven wiring/kinematics).
 *   FL = X (2,5)  FR = Y (3,6)  RL = Z (4,7) POL -1  RR = A (12,A0)  EN 8
 *   Mix: FL = fwd+side  FR = fwd-side  RL = fwd-side  RR = fwd+side
 *   NOTE the +side on FL. Flipping it sends every diagonal down the wrong axis.
 *
 * SENSORS: A0 is RR's direction pin, so the echoes route around it and use
 *   A2 (Resume) instead — A2 is free now that Y-DIR lives on D6.
 *     TRIG (all three, one shared wire) -> D9   (X+ endstop)
 *     ECHO front       D10 (Y+ endstop)   ECHO left-front  A1 (Hold)
 *     ECHO right-front A2  (Resume)
 *     (rear pair removed - A3/A4 are free again)
 * SERVO: REMOVED. Camera is fixed-mount; D11 is free.
 * SPARE: D11, D13, A3, A4, A5, D0, D1
 *
 * SERIAL 115200
 *   v <vx> <vy> <w>   -100..100 each   vx fwd, vy right, w clockwise
 *   f b l r q e s     manual keys       + -   speed step
 *   m <corner> <spd>  one motor: 0=FL 1=FR 2=RL 3=RR
 *   t <n>             accepted, ignored (servo removed)
 *   c                 crab circle (~30 cm)      ?  report state
 *   OUT: "us f=52 lf=110 rf=0"  cm, 0 = no echo, ~11 Hz with 3 sensors
 *
 * SAFETY, both on the Uno so neither depends on WiFi:
 *   - v-mode stops if the Pi goes quiet 500 ms
 *   - forward motion refused under 25 cm front clearance
 */
#include <AccelStepper.h>
#include <math.h>

AccelStepper FL(AccelStepper::DRIVER, 2, 5);    // X  top-left
AccelStepper FR(AccelStepper::DRIVER, 3, 6);    // Y  top-right
AccelStepper RL(AccelStepper::DRIVER, 4, 7);    // Z  bottom-left
AccelStepper RR(AccelStepper::DRIVER, 12, A0);  // A  bottom-right (A0 = Abort)
AccelStepper* M[4] = { &FL, &FR, &RL, &RR };
const float POL[4] = { +1, +1, -1, +1 };        // RL inverted in hardware

const int ENABLE_PIN = 8;
// Steps per rev depends on the MS1/MS2/MS3 jumpers under each A4988:
//   no jumpers = 200 (full step, loudest)   1/2 = 400   1/4 = 800
//   1/8 = 1600   1/16 = 3200 (quietest, but needs a high pulse rate)
// Microstepping is the real cure for stepper noise. Change this to match
// the jumpers you fit, or the speed scale will be wrong by that factor.
const float STEPS_PER_REV = 200.0;
const float WHEEL_CIRC_M  = 0.0600 * M_PI;      // 60 mm wheels

// Steppers have loud and quiet speed bands (mechanical resonance), so the
// top rate is tunable at runtime with 'k <steps/s>' - no reflash needed to
// hunt for the quiet spot. Raised from 318 to give real headroom.
float MAX_SPS = 520.0;
const float MAX_SPS_CEILING = 1400.0;           // beyond this it just stalls

// Crab circle, 2 ft radius.
//   Peak wheel rate = amp*sqrt(2)*MAX_SPS and steppers STALL if commanded
//   above what they can start at. Your original sketch proved 264 steps/s,
//   so the lap time is chosen to land there. A shorter lap = faster = stall.
//   amp is also capped at 1/sqrt(2) so setVel()'s normaliser never clips the
//   sweep; clipping would flatten the fast quadrants into an oval.
const float CIRCLE_RADIUS_M = 0.3048;           // 1 ft radius = 2 ft ACROSS
const float SECONDS_PER_LAP = 11.0;             // -> ~261 steps/s peak
const float CRAB_RAMP_S     = 0.8;              // ease in/out, no stall on start
const int   CRAB_SLICE_MS   = 5;                // 4400 vector updates per lap

const int TRIG = 9;
// Three FRONT sensors only. The two rear ones were dropped: the robot never
// reverses autonomously, so rear echoes cost scan time (each ping blocks up
// to the echo timeout) and bought nothing. Fewer sensors = faster loop = the
// front reading, which is the one the veto depends on, refreshes sooner.
const int NUS = 3;
const int ECHO[NUS] = { 10, A1, A2 };           // f, lf, rf
const char* USNAME[NUS] = { "f", "lf", "rf" };
const int FRONT = 0, VETO_CM = 25;
// The front-obstacle veto is OFF until the sensors are proven. An interlock
// fed by garbage data just blocks legitimate driving: a rail glitch pinned
// the front reading at 5 cm and forward stopped working entirely.
//   Armed by default now that the sensors read reliably. 'g 0' disarms.
//   Needs two consecutive close reads
//   plus a plausible distance (HC-SR04 cannot resolve under ~2 cm).
bool guardOn = true;    // obstacle avoidance armed at boot
int  frontHits = 0;
const int VETO_MIN_CM = 3, VETO_CONFIRM = 2;
int usCM[NUS] = { 0, 0, 0 };
int usIdx = 0;
// Median-of-3 per sensor. A shared TRIG means all five ping at once, so a
// sensor occasionally hears a neighbour's burst before its own return and
// reports a wild short value. A median rejects that single outlier while
// still tracking real movement.
int usHist[NUS][3] = {{0}};
byte usSlot[NUS] = { 0, 0, 0 };

int median3(int a, int b, int c) {
  if (a > b) { int t = a; a = b; b = t; }
  if (b > c) { int t = b; b = c; c = t; }
  if (a > b) { int t = a; a = b; b = t; }
  return b;
}


float curVX = 0, curVY = 0, curW = 0;
int speedPct = 60;
bool vMode = false;
unsigned long lastV = 0, lastPing = 0, lastReport = 0;
char line[40];
byte lineLen = 0;

// A stepper cannot START at its running speed. Pull-in torque collapses with
// rate, so commanding 0 -> 520 sps in one step makes a loaded wheel slip
// instead of turn. Whichever wheels slip, the robot rotates: on a strafe all
// four are fighting roller friction, so it shows up there first and worst.
// Targets are therefore ramped toward, not jumped to.
float wheelTgt[4] = {0, 0, 0, 0};    // what the mix asked for, sps
float wheelCur[4] = {0, 0, 0, 0};    // what the motors are actually running
unsigned long lastSlewUs = 0;
// Full scale in ~0.13 s. The first 20 ms tick asks for about 80 sps, still
// far inside pull-in, but the robot answers the button quickly enough that it
// does not feel laggy. 'a' lowers it if a wheel ever slips again.
float SLEW_SPS_PER_S = 4000.0;

void setVel(float vx, float vy, float w) {
  if (guardOn && vx > 0 && frontHits >= VETO_CONFIRM) vx = 0;   // veto
  curVX = vx; curVY = vy; curW = w;
  float s[4];
  s[0] = vx + vy + w;      // FL
  s[1] = vx - vy - w;      // FR
  s[2] = vx - vy + w;      // RL
  s[3] = vx + vy - w;      // RR
  float mx = 0;
  for (int i = 0; i < 4; i++) mx = max(mx, fabs(s[i]));
  if (mx > 1.0) for (int i = 0; i < 4; i++) s[i] /= mx;
  for (int i = 0; i < 4; i++) wheelTgt[i] = POL[i] * s[i] * MAX_SPS;
}

void applySlew() {
  unsigned long now = micros();
  float dt = (now - lastSlewUs) / 1000000.0f;
  lastSlewUs = now;
  if (dt <= 0 || dt > 0.25f) dt = 0.01f;      // first call, or a long stall
  float step = SLEW_SPS_PER_S * dt;
  for (int i = 0; i < 4; i++) {
    float t = wheelTgt[i], c = wheelCur[i];
    bool opposing = (t > 0 && c < 0) || (t < 0 && c > 0);
    if (opposing) {
      // A full reversal is a bigger jump than starting from rest, so drop to
      // zero this tick and ramp up the other way from there.
      c = 0;
    } else if (fabs(t) <= fabs(c)) {
      // Slowing never stalls a stepper, and STOP has to stay instant.
      c = t;
    } else if (t - c >  step) {
      c += step;
    } else if (t - c < -step) {
      c -= step;
    } else {
      c = t;
    }
    wheelCur[i] = c;
    M[i]->setSpeed(c);
  }
}

void runAll() { for (int i = 0; i < 4; i++) M[i]->runSpeed(); }

// pulseIn() blocks, so its timeout is stolen from stepper pulse generation.
// Standing still that costs nothing, so use the sensor's full ~4 m range;
// while driving, cap at ~1 m so the stall stays an inaudible blip.
unsigned long echoTimeoutUs() {
  applySlew();      // step the wheels toward their target before running them

  bool moving = (fabs(curVX) + fabs(curVY) + fabs(curW)) > 0.05;
  return moving ? 6000UL : 23000UL;
}

void pingOne(int i) {
  digitalWrite(TRIG, LOW);  delayMicroseconds(4);
  digitalWrite(TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  unsigned long us = pulseIn(ECHO[i], HIGH, echoTimeoutUs());
  int raw = us ? (int)(us / 58) : 0;
  usHist[i][usSlot[i]] = raw;
  usSlot[i] = (usSlot[i] + 1) % 3;
  usCM[i] = median3(usHist[i][0], usHist[i][1], usHist[i][2]);
  if (i == FRONT) {
    bool close = (usCM[FRONT] >= VETO_MIN_CM && usCM[FRONT] < VETO_CM);
    frontHits = close ? frontHits + 1 : 0;
    if (guardOn && curVX > 0 && frontHits >= VETO_CONFIRM)
      setVel(0, curVY, curW);
  }
}

void crabCircle() {
  // The 'c' arrives as "c\n". Without this flush the trailing newline is
  // still buffered, the abort check below sees it on the very first pass,
  // and the circle cancels itself after one 5 ms slice -> a twitch.
  delay(5);
  while (Serial.available()) Serial.read();
  Serial.println("crab start");
  float V      = (2.0 * M_PI * CIRCLE_RADIUS_M) / SECONDS_PER_LAP;   // m/s
  float topMs  = MAX_SPS * WHEEL_CIRC_M / STEPS_PER_REV;   // current full-scale
  float amp    = min(V / topMs, 0.7071f);        // cap: keep peak <= 1.0
  unsigned long t0 = micros();
  float lapUs = SECONDS_PER_LAP * 1e6;
  while ((float)(micros() - t0) < lapUs) {
    float t   = (float)(micros() - t0) / 1e6;
    float ang = 2.0 * M_PI * t / SECONDS_PER_LAP;
    // ease in and out so the motors are never asked to start at full rate
    float ramp = min(1.0f, min(t / CRAB_RAMP_S,
                               (SECONDS_PER_LAP - t) / CRAB_RAMP_S));
    setVel(amp * ramp * sin(ang), amp * ramp * cos(ang), 0);  // body stays put
    unsigned long slice = millis();
    while (millis() - slice < CRAB_SLICE_MS) { runAll(); yield(); }
    // Don't consume the byte: break and let loop() parse it, so STOP works.
    if (Serial.available()) break;
  }
  setVel(0, 0, 0);
  Serial.println("crab done");
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
    // Servo removed - the camera is bolted at a fixed angle now. The command
    // is still accepted so an older Pi build cannot wedge on an unknown key.
  } else if (c == 'k') {
    // k <steps/s> : set the full-scale wheel rate. Higher = faster, and the
    // noise changes sharply with it - sweep to find the quiet band.
    long v = strtol(line + 1, NULL, 10);
    if (v >= 60 && v <= (long)MAX_SPS_CEILING) {
      MAX_SPS = (float)v;
      setVel(curVX, curVY, curW);        // re-apply at the new scale
    }
    Serial.print("maxsps="); Serial.println(MAX_SPS);
  } else if (c == 'a') {
    // a <sps/s> : how hard the wheels are allowed to accelerate. Lower it if
    // a strafe still slips, raise it if the robot feels sluggish.
    long v = strtol(line + 1, NULL, 10);
    if (v >= 300 && v <= 20000) SLEW_SPS_PER_S = (float)v;
    Serial.print("slew="); Serial.println(SLEW_SPS_PER_S);
  } else if (c == 'g') {
    guardOn = (strtol(line + 1, NULL, 10) != 0);
    Serial.print("guard="); Serial.println(guardOn ? "ON" : "OFF");
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
      Serial.print(" spd="); Serial.print(speedPct);
      Serial.print(" guard="); Serial.print(guardOn ? "ON" : "OFF");
      Serial.print(" maxsps="); Serial.print(MAX_SPS);
      Serial.print(" m/s="); Serial.println(MAX_SPS * WHEEL_CIRC_M / STEPS_PER_REV);
    }
    else if (c == '+' || c == '-')
      speedPct = constrain(speedPct + (c == '+' ? 10 : -10), 20, 100);
  }
  lineLen = 0;
}

void setup() {
  Serial.begin(115200);
  pinMode(ENABLE_PIN, OUTPUT); digitalWrite(ENABLE_PIN, LOW);
  // setMaxSpeed must cover the ceiling, not today's MAX_SPS, or a later
  // 'k' command would be silently clamped to the old limit.
  for (int i = 0; i < 4; i++) {
    M[i]->setMaxSpeed(MAX_SPS_CEILING * 1.6);
    M[i]->setSpeed(0);
  }
  pinMode(TRIG, OUTPUT); digitalWrite(TRIG, LOW);
  for (int i = 0; i < NUS; i++) pinMode(ECHO[i], INPUT_PULLDOWN);  // unwired = 0, not noise
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

  applySlew();      // step the wheels toward their target before running them

  bool moving = (fabs(curVX) + fabs(curVY) + fabs(curW)) > 0.05;
  // >=60 ms between TRIG pulses: with one shared trigger wire the tick rate
  // IS each sensor's re-trigger rate. 30 ms was re-firing them mid-echo.
  if (millis() - lastPing >= (unsigned long)(moving ? 150 : 70)) {
    lastPing = millis();
    pingOne(usIdx);
    usIdx = (usIdx + 1) % 5;
  }

  if (millis() - lastReport >= 140) {
    lastReport = millis();
    Serial.print("us");
    for (int i = 0; i < NUS; i++) {
      Serial.print(' '); Serial.print(USNAME[i]);
      Serial.print('='); Serial.print(usCM[i]);
    }
    Serial.println();
  }

  if (vMode && millis() - lastV > 500) { setVel(0, 0, 0); vMode = false; }

  runAll();
  yield();
}
