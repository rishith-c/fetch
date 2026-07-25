/*
 * FETCH STEPPERS — Pi-controllable drive. Motors only (no servo/sonar yet).
 *
 * WIRING + KINEMATICS TAKEN VERBATIM from the user's known-good crab sketch:
 *   FL = X socket (2,5)   top-left        POL +1
 *   FR = Y socket (3,6)   top-right       POL +1
 *   RL = Z socket (4,7)   bottom-left     POL -1   <-- hardware correction
 *   RR = A socket (12,A0) bottom-right    POL +1
 *   ENABLE 8.  AccelStepper velocity mode + runSpeed(), which is what makes
 *   the motion smooth (no ramps, no stalls, no hexagon).
 *
 * Their mix, with fwd = forward and side = sideways:
 *     FL = fwd + side      FR = fwd - side
 *     RL = fwd - side      RR = fwd + side
 * NOTE the SIGN: FL gets +side. An earlier version of this file used -side,
 * which sent every diagonal down the wrong axis. Do not "fix" it back.
 * The w (rotation) term is the only thing added here: spin-right needs the
 * left wheels forward and the right wheels back.
 *
 * PINS FREE for the sensors/servo later: 9, 10, 11, 13, A1..A5, D0, D1
 *   (A0 is now RR direction, A2 is free again.)
 *
 * SERIAL 115200
 *   v <vx> <vy> <w>   each -100..100   vx fwd, vy right, w clockwise
 *   f b l r q e s     manual keys        + -   speed step
 *   m <corner> <spd>  ONE motor: 0=FL 1=FR 2=RL 3=RR   (calibration)
 *   c                 crab circle, ~30 cm across
 *   ?                 report state
 * Motors stop themselves if v-mode goes quiet for 500 ms.
 */
#include <AccelStepper.h>
#include <math.h>

AccelStepper FL(AccelStepper::DRIVER, 2, 5);    // X  top-left
AccelStepper FR(AccelStepper::DRIVER, 3, 6);    // Y  top-right
AccelStepper RL(AccelStepper::DRIVER, 4, 7);    // Z  bottom-left
AccelStepper RR(AccelStepper::DRIVER, 12, A0);  // A  bottom-right
AccelStepper* M[4] = { &FL, &FR, &RL, &RR };
const float POL[4] = { +1, +1, -1, +1 };        // RL inverted in hardware

const int ENABLE_PIN = 8;

// speed scale, derived the same way as the crab sketch
const float STEPS_PER_REV = 200.0;              // full-step; 1600 if microstepping
const float WHEEL_CIRC_M  = 0.0600 * M_PI;      // 60 mm wheels
const float MAX_MS        = 0.30;               // m/s at 100 %
const float MAX_SPS       = MAX_MS * (STEPS_PER_REV / WHEEL_CIRC_M);

// crab circle: 2 ft radius. Lap time sets the speed (V = 2*pi*R / T), and
// the vector is refreshed every 5 ms -> ~3200 updates per lap, so the path
// is a continuous circle, not a polygon.
const float CIRCLE_RADIUS_M = 0.6096;           // 2 ft
const float SECONDS_PER_LAP = 16.0;
const int   CRAB_SLICE_MS   = 5;

float curVX = 0, curVY = 0, curW = 0;
int speedPct = 60;
bool vMode = false;
unsigned long lastV = 0;
char line[40];
byte lineLen = 0;

// vx forward, vy right, w clockwise — all -1..1
void setVel(float vx, float vy, float w) {
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

void crabCircle() {
  float V   = (2.0 * M_PI * CIRCLE_RADIUS_M) / SECONDS_PER_LAP;   // m/s
  float amp = min(1.0f, (float)(V / MAX_MS));
  unsigned long t0 = micros();
  float lapUs = SECONDS_PER_LAP * 1e6;
  while ((float)(micros() - t0) < lapUs) {
    // micros() keeps the angle smooth between refreshes; no quantised steps
    float ang = 2.0 * M_PI * (float)(micros() - t0) / lapUs;
    setVel(amp * sin(ang), amp * cos(ang), 0);   // body never rotates
    unsigned long slice = millis();
    while (millis() - slice < CRAB_SLICE_MS) { runAll(); yield(); }
    // Do NOT consume the byte: break and let loop() parse it, so a STOP
    // actually stops instead of being swallowed here.
    if (Serial.available()) break;
  }
  setVel(0, 0, 0);
}

void handleLine() {
  line[lineLen] = 0;
  char c = line[0];
  if (c == 'v') {
    // strtol, NOT sscanf: newlib-nano on this core has no %f in scanf, so
    // "%f" silently parsed every velocity as zero and nothing ever moved.
    char *p = line + 1;
    long v[3] = { 0, 0, 0 };
    for (int i = 0; i < 3; i++) v[i] = strtol(p, &p, 10);
    setVel(v[0] / 100.0f, v[1] / 100.0f, v[2] / 100.0f);
    vMode = true; lastV = millis();
  } else if (c == 'm') {
    // m <corner 0=FL 1=FR 2=RL 3=RR> <spd -100..100> — one motor alone
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
      Serial.print(" maxsps="); Serial.println(MAX_SPS);
    }
    else if (c == '+' || c == '-')
      speedPct = constrain(speedPct + (c == '+' ? 10 : -10), 20, 100);
  }
  lineLen = 0;
}

void setup() {
  Serial.begin(115200);
  pinMode(ENABLE_PIN, OUTPUT);
  digitalWrite(ENABLE_PIN, LOW);               // LOW = drivers enabled
  float top = MAX_SPS * 1.6;                   // cover the diagonal peak
  for (int i = 0; i < 4; i++) { M[i]->setMaxSpeed(top); M[i]->setSpeed(0); }
  Serial.println("FETCH STEPPERS READY");
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

  if (vMode && millis() - lastV > 500) { setVel(0, 0, 0); vMode = false; }

  runAll();
  yield();
}
