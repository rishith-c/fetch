/*
 * FETCH — drive controller firmware
 * Arduino Uno R4 (Minima or WiFi) + CNC Shield V3 + 4x A4988 + 4x NEMA17
 *
 * ROLE
 *   Take (vx, vy, omega) from the Pi over USB serial. Mix it into 4 mecanum
 *   wheel speeds. Pulse the steppers. Independently watch five HC-SR04 sensors
 *   and veto motion that would drive into an obstacle.
 *
 *   Safety NEVER depends on WiFi, the Pi, or the phone. The veto lives here.
 *
 * LIBRARY
 *   AccelStepper  (Tools > Manage Libraries > "AccelStepper")
 *
 * ---------------------------------------------------------------------------
 * CONSTANTS THAT CAME OUT OF SIMULATION — do not "improve" these
 * ---------------------------------------------------------------------------
 *   MICROSTEP = 4
 *       AccelStepper holds ~10k steps/sec AGGREGATE across all 4 motors on a
 *       48MHz R4. Straight-line driving runs all four flat out, so that ceiling
 *       binds. Max speed by microstep:
 *           1/1  -> 3142 mm/s   (loud, resonance)
 *           1/2  -> 1571 mm/s
 *           1/4  ->  785 mm/s   <-- USE THIS
 *           1/8  ->  393 mm/s   (speed-capped)
 *           1/16 ->  196 mm/s   (unusably slow)
 *       Set the SAME jumpers on ALL FOUR drivers, including the A socket.
 *       Mismatched microstepping makes the mixing math wrong and the robot curves.
 *
 *   MAX_SPEED_MMS = 250      keeps aggregate ~3.2k steps/s, inside the ceiling
 *   MAX_STRAFE_MMS = 150     bounded by how fast the side sensors can see
 *   SLEW_MMS2 = 500          JK42HS40-1704-13A (0.42Nm) + 2.94kg mass
 *                            gives ~4000 mm/s^2; slow sonar build stays conservative.
 *
 *   THE SLEW LIMITER IS NOT OPTIONAL. AccelStepper's setSpeed()/runSpeed() is
 *   CONSTANT-SPEED mode: it applies speed instantly and IGNORES
 *   setAcceleration(). A stepper cannot jump 0->500mm/s under load; it skips
 *   steps and buzzes. We ramp the commanded velocity ourselves in updateSlew().
 * ---------------------------------------------------------------------------
 */

#include <AccelStepper.h>

// ---------------------------------------------------------------------------
// Final sensor configuration. HC-SR04 and Uno R4 both use 5V logic, so no
// level shifter is needed. Short pulseIn() timeouts bound step-pulse disruption.
#define USE_ULTRASONICS 1

// Compatibility assertion consumed by the audits. TF-Luna hardware and code
// are intentionally absent from the final build.
#define USE_TFLUNA 0

// ---------------- pin map ----------------
// CNC Shield V3 fixes X/Y/Z step+dir and the shared ENABLE. We are not running
// GRBL, so the shield's limit-switch / spindle headers are free breakouts.
#define M_FL_STEP 2
#define M_FL_DIR  5
#define M_FR_STEP 3
#define M_FR_DIR  6
#define M_RL_STEP 4
#define M_RL_DIR  7
// 4th motor -> the shield's "A" SOCKET. NOT hand-wired: the V3 has FOUR
// sockets (X, Y, Z, A). Set the bottom-left jumper block to D12/D13 —
// NOT clone-X/Y/Z, we need it independent for mecanum. This costs you
// SpnEn/SpnDir, which we never use.
#define M_RR_STEP 12
#define M_RR_DIR  13
#define EN_PIN    8       // LOW = drivers enabled

#if USE_ULTRASONICS
// Five independent HC-SR04s. Removing the TF-Luna frees A4/A5, so no trigger
// has to be shared and acoustic crosstalk is reduced.
//   US1   0 deg FRONT       D9/D10
//   US2  75 deg LEFT-FRONT  D11/A0
//   US3 145 deg LEFT-REAR   A1/A2
//   US4 215 deg RIGHT-REAR  A3/D0
//   US5 285 deg RIGHT-FRONT D1/A4
#define US_N 5
const uint8_t US_TRIG[US_N] = { 9, 11, A1, A3, 1 };
const uint8_t US_ECHO[US_N] = { 10, A0, A2, 0, A4 };
const char*   US_NAME[US_N] = { "front", "L-front", "L-rear", "R-rear", "R-front" };
#endif

// ---------------- geometry ----------------
const float WHEEL_DIA_MM  = 80.0;      // <-- CHANGE IF YOUR WHEELS DIFFER
const float WHEEL_CIRC_MM = 3.14159265f * WHEEL_DIA_MM;
const int   STEPS_PER_REV = 200;       // NEMA17 1.8deg
const int   MICROSTEP     = 4;         // see header. Do not raise.
const float STEPS_PER_MM  = (STEPS_PER_REV * MICROSTEP) / WHEEL_CIRC_MM;

const float MAX_SPEED_MMS  = 250.0;
const float MAX_STRAFE_MMS = 150.0;
const float SLEW_MMS2      = 500.0;

// ---------------- safety ----------------
#if USE_ULTRASONICS
const int FRONT_STOP_CM = 60;
const int SIDE_STOP_CM  = 35;
#endif
const unsigned long CMD_TIMEOUT_MS = 500;   // Pi goes quiet -> stop

// ---------------- steppers ----------------
AccelStepper mFL(AccelStepper::DRIVER, M_FL_STEP, M_FL_DIR);
AccelStepper mFR(AccelStepper::DRIVER, M_FR_STEP, M_FR_DIR);
AccelStepper mRL(AccelStepper::DRIVER, M_RL_STEP, M_RL_DIR);
AccelStepper mRR(AccelStepper::DRIVER, M_RR_STEP, M_RR_DIR);

// ---------------- state ----------------
float cmdVx = 0, cmdVy = 0, cmdW = 0;   // what the Pi asked for
float curVx = 0, curVy = 0, curW = 0;   // what we're applying (ramped)
unsigned long lastCmdMs = 0, lastSlewUs = 0;
int  frontDist = 999;
#if USE_ULTRASONICS
int  usDist[US_N];
#else
int  usDist[4] = { 999, 999, 999, 999 };
#endif
uint8_t sideUsIdx = 1;
unsigned long lastFrontUsMs = 0, lastSideUsMs = 0, lastTxMs = 0;
bool estop = false;

#if USE_ULTRASONICS
// Short timeout on purpose: we only care about obstacles inside ~60cm, so cap
// the blocking at ~3.5ms instead of pulseIn's 1s default. Long blocking here
// starves the step pulses and the motors stutter.
void pollOneUltrasonic(uint8_t i) {
  digitalWrite(US_TRIG[i], LOW);  delayMicroseconds(2);
  digitalWrite(US_TRIG[i], HIGH); delayMicroseconds(10);
  digitalWrite(US_TRIG[i], LOW);
  unsigned long dur = pulseIn(US_ECHO[i], HIGH, 3500UL);
  usDist[i] = (dur == 0) ? 999 : (int)(dur / 58);
}
#endif

// ---------------- obstacle veto ----------------
// Runs regardless of what the Pi asks for. This is the hard guarantee.
void applyObstacleVeto(float &vx, float &vy, float &w) {
  if (estop) { vx = vy = w = 0; return; }
#if USE_ULTRASONICS
  // ring: 0=front 1=L-front 2=L-rear 3=R-rear 4=R-front
  if (frontDist < FRONT_STOP_CM && vx > 0) vx = 0;
  if ((usDist[2] < SIDE_STOP_CM || usDist[3] < SIDE_STOP_CM) && vx < 0) vx = 0;
  if ((usDist[1] < SIDE_STOP_CM || usDist[2] < SIDE_STOP_CM) && vy > 0) vy = 0;
  if ((usDist[3] < SIDE_STOP_CM || usDist[4] < SIDE_STOP_CM) && vy < 0) vy = 0;
  for (int i = 1; i < US_N; i++) if (usDist[i] < 20) w = 0;
#endif
}

// ---------------- slew limiter ----------------
static float slewToward(float cur, float target, float maxDelta) {
  float d = target - cur;
  if (d >  maxDelta) return cur + maxDelta;
  if (d < -maxDelta) return cur - maxDelta;
  return target;
}

void updateSlew(float tvx, float tvy, float tw) {
  unsigned long nowUs = micros();
  float dt = (nowUs - lastSlewUs) / 1000000.0f;
  lastSlewUs = nowUs;
  if (dt <= 0 || dt > 0.2f) dt = 0.001f;      // guard first call / stalls
  float maxDelta = SLEW_MMS2 * dt;
  curVx = slewToward(curVx, tvx, maxDelta);
  curVy = slewToward(curVy, tvy, maxDelta);
  curW  = slewToward(curW,  tw,  maxDelta);
}

// ---------------- mecanum mix ----------------
void driveMix(float vx, float vy, float w) {
  float fl = vx - vy - w;
  float fr = vx + vy + w;
  float rl = vx + vy - w;
  float rr = vx - vy + w;
  // Scale together if any wheel exceeds max — preserves the motion VECTOR.
  // Clipping each wheel independently would change the direction of travel.
  float peak = max(max(fabs(fl), fabs(fr)), max(fabs(rl), fabs(rr)));
  if (peak > MAX_SPEED_MMS) {
    float k = MAX_SPEED_MMS / peak;
    fl *= k; fr *= k; rl *= k; rr *= k;
  }
  mFL.setSpeed(fl * STEPS_PER_MM);
  mFR.setSpeed(fr * STEPS_PER_MM);
  mRL.setSpeed(rl * STEPS_PER_MM);
  mRR.setSpeed(rr * STEPS_PER_MM);
}

// ---------------- serial protocol ----------------
// Pi -> Uno :  "V <vx> <vy> <w>\n"   mm/s mm/s deg/s
//              "E\n"  estop latch     "C\n"  clear estop
// Uno -> Pi : "S <front> <us0..us4> <estop>\n" @10Hz
char buf[48];
uint8_t bufLen = 0;

void handleLine(char *line) {
  if (line[0] == 'V') {
    float a, b, c;
    if (sscanf(line + 1, "%f %f %f", &a, &b, &c) == 3) {
      cmdVx = constrain(a, -MAX_SPEED_MMS,  MAX_SPEED_MMS);
      cmdVy = constrain(b, -MAX_STRAFE_MMS, MAX_STRAFE_MMS);
      cmdW  = constrain(c, -MAX_SPEED_MMS,  MAX_SPEED_MMS);
      lastCmdMs = millis();
    }
  } else if (line[0] == 'E') {
    estop = true;
  } else if (line[0] == 'C') {
    estop = false; lastCmdMs = millis();
  }
}

void pumpSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (bufLen) { buf[bufLen] = 0; handleLine(buf); bufLen = 0; }
    } else if (bufLen < sizeof(buf) - 1) {
      buf[bufLen++] = c;
    }
  }
}

// ---------------- setup / loop ----------------
void setup() {
  Serial.begin(115200);            // USB-C to the Pi -> /dev/ttyACM0
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, HIGH);      // start DISABLED — motors free until commanded

#if USE_ULTRASONICS
  for (int i = 0; i < US_N; i++) {
    usDist[i] = 999;
    pinMode(US_TRIG[i], OUTPUT);
    pinMode(US_ECHO[i], INPUT);       // INPUT, not INPUT_PULLUP: we are not GRBL
    digitalWrite(US_TRIG[i], LOW);
  }
#endif

  // No setAcceleration(): runSpeed() ignores it. We ramp in updateSlew().
  AccelStepper* all[4] = { &mFL, &mFR, &mRL, &mRR };
  for (int i = 0; i < 4; i++) {
    all[i]->setMaxSpeed(MAX_SPEED_MMS * STEPS_PER_MM * 2);   // we clamp in the mix
    all[i]->setSpeed(0);
  }

  digitalWrite(EN_PIN, LOW);       // enable drivers
  lastCmdMs = millis();
  lastSlewUs = micros();
}

void loop() {
  unsigned long now = millis();
  pumpSerial();

  // --- sensors, staggered so neither starves the step pulses ---
#if USE_ULTRASONICS
  if (now - lastFrontUsMs >= 50) {              // dedicated front at 20Hz
    lastFrontUsMs = now;
    pollOneUltrasonic(0);
    frontDist = usDist[0];
  }
  if (now - lastSideUsMs >= 80) {               // one corner per 80ms
    lastSideUsMs = now;
    pollOneUltrasonic(sideUsIdx);
    sideUsIdx++;
    if (sideUsIdx >= US_N) sideUsIdx = 1;
  }
#endif

  // --- watchdog: Pi went quiet -> stop ---
  float vx = cmdVx, vy = cmdVy, w = cmdW;
  if (now - lastCmdMs > CMD_TIMEOUT_MS) { vx = vy = w = 0; }

  // Veto BEFORE slewing, so a blocked axis ramps down instead of snapping to
  // zero and skipping steps.
  applyObstacleVeto(vx, vy, w);
  updateSlew(vx, vy, w);
  driveMix(curVx, curVy, curW);

  // --- telemetry ---
  if (now - lastTxMs >= 100) {
    lastTxMs = now;
    // First distance is always the dedicated forward range used by the Pi for
    // checkpoint arrival. It remains protocol-compatible with older clients.
    Serial.print("S "); Serial.print(frontDist);
#if USE_ULTRASONICS
    for (int i = 0; i < US_N; i++) { Serial.print(' '); Serial.print(usDist[i]); }
#else
    for (int i = 0; i < 4; i++) { Serial.print(' '); Serial.print(usDist[i]); }
#endif
    Serial.print(' '); Serial.println(estop ? 1 : 0);
  }

  // --- pulse. must run as often as possible ---
  mFL.runSpeed();
  mFR.runSpeed();
  mRL.runSpeed();
  mRR.runSpeed();
}
