#include <AccelStepper.h>
#include <math.h>

// ------------ Custom Wiring Layout Maintained -------------
AccelStepper FL(AccelStepper::DRIVER, 2, 5);   // X  Top Left
AccelStepper FR(AccelStepper::DRIVER, 3, 6);   // Y  Top Right
AccelStepper RL(AccelStepper::DRIVER, 4, 7);   // Z  Bottom Left (inverted, kept)
AccelStepper RR(AccelStepper::DRIVER, 12, A0); // A  Bottom Right (A0 kept)

#define ENABLE_PIN 8

// ---------------- CRAB CIRCLE TUNING ----------------
const float CIRCLE_DIAMETER_M = 0.30;  // ~1 ft circle
const float SECONDS_PER_LAP   = 4.0;   // lower = faster (2.5 is spicy)
const int   LAPS              = 2;     // 0 = circle forever

// your drivetrain: 80mm wheels, 200 steps/rev at full-step
// (if it barely creeps or screams, you're microstepping: try 1600)
const float STEPS_PER_REV = 200.0;
const float WHEEL_CIRC_M  = 0.0800 * M_PI;

// per-wheel polarity — encodes your "rl = -rl" hardware correction
const float POL_FL = +1, POL_FR = +1, POL_RL = -1, POL_RR = +1;

float SPS;            // wheel speed amplitude, steps/sec
unsigned long t0;

void setup() {
  pinMode(ENABLE_PIN, OUTPUT);
  digitalWrite(ENABLE_PIN, LOW);

  // translation speed V = pi * D / T, converted to steps/sec
  float V = (M_PI * CIRCLE_DIAMETER_M) / SECONDS_PER_LAP;       // m/s
  SPS = V * (STEPS_PER_REV / WHEEL_CIRC_M);                     // steps/s

  // velocity mode: max speed must cover the sqrt(2) diagonal peak
  float top = SPS * 1.5;
  FL.setMaxSpeed(top); FR.setMaxSpeed(top);
  RL.setMaxSpeed(top); RR.setMaxSpeed(top);

  delay(1500);
  t0 = millis();
}

void loop() {
  float t = (millis() - t0) / 1000.0;

  // stop cleanly after LAPS (if LAPS > 0)
  if (LAPS > 0 && t > LAPS * SECONDS_PER_LAP) {
    FL.setSpeed(0); FR.setSpeed(0); RL.setSpeed(0); RR.setSpeed(0);
    digitalWrite(ENABLE_PIN, HIGH);          // release motors
    while (true) yield();
  }

  // heading around the circle — velocity vector rotates continuously
  float ang = 2.0 * M_PI * t / SECONDS_PER_LAP;
  float vx = SPS * cos(ang);                 // sideways component
  float vy = SPS * sin(ang);                 // forward component

  // same mecanum mapping as your code, but as SPEEDS not positions
  FL.setSpeed(POL_FL * (vy + vx));
  FR.setSpeed(POL_FR * (vy - vx));
  RL.setSpeed(POL_RL * (vy - vx));
  RR.setSpeed(POL_RR * (vy + vx));

  // pulse all four hard for ~12 ms, then refresh the velocity vector.
  // runSpeed() = constant-rate stepping: no ramps, no stops, no hexagon.
  unsigned long slice = millis();
  while (millis() - slice < 12) {
    FL.runSpeed(); FR.runSpeed(); RL.runSpeed(); RR.runSpeed();
    yield();
  }
}