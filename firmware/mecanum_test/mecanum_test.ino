/*
 * FETCH — mecanum drive test.  Uno + CNC Shield V3 + 4x A4988 + 4x NEMA17.
 *
 * Self-contained (no Pi). Drives the mecanum base so you can confirm the whole
 * drivetrain and CALIBRATE wheel directions.
 *
 *   DEMO = 0 : drive FORWARD forever (simplest "spin all 4 to move")
 *   DEMO = 1 : cycle forward / back / strafe L / strafe R / rotate / stop
 *
 * ---- THE ONE THING YOU MUST CALIBRATE: INVERT[] ----
 * Mecanum motors are mirror-mounted, so a raw DIR pin means "forward" on one
 * side and "backward" on the other. I can't know your wiring, so:
 *   1. Upload with DEMO 0.  Watch the wheels during FORWARD.
 *   2. ANY wheel rolling the wrong way -> flip that wheel's sign in INVERT[]
 *      (+1 <-> -1), re-upload. Repeat until all four roll the robot forward.
 * Once forward is right, strafe and rotate are automatically right too.
 *
 * BEFORE UPLOADING: motors plugged in with POWER OFF, then 12V + USB on,
 * Vref already set on all four drivers. Needs the AccelStepper library.
 */
#include <AccelStepper.h>

#define DEMO 0

// CNC Shield V3 sockets:            step dir
AccelStepper FL(AccelStepper::DRIVER,  2,  5);   // X  front-left
AccelStepper FR(AccelStepper::DRIVER,  3,  6);   // Y  front-right
AccelStepper RL(AccelStepper::DRIVER,  4,  7);   // Z  rear-left
AccelStepper RR(AccelStepper::DRIVER, 12, 13);   // A  rear-right (jumper D12/D13)
AccelStepper* M[4] = { &FL, &FR, &RL, &RR };
const int EN = 8;                                 // LOW = drivers on

// FL, FR, RL, RR.  Flip a sign if that wheel spins the wrong way. Default is
// the usual left/right mirror.
int INVERT[4] = { +1, -1, +1, -1 };

const float VMAX  = 600.0;   // steps/sec — gentle test speed (works on R3 too)
const float ACCEL = 900.0;   // steps/sec^2 software slew — stops the screaming

float target[4] = {0,0,0,0}, cur[4] = {0,0,0,0};
unsigned long tLast, tPhase;
int phase = 0;

// mecanum mixing: vx fwd, vy left, w ccw   (each -1..+1)
void drive(float vx, float vy, float w) {
  target[0] = (vx - vy - w) * VMAX * INVERT[0];   // FL
  target[1] = (vx + vy + w) * VMAX * INVERT[1];   // FR
  target[2] = (vx + vy - w) * VMAX * INVERT[2];   // RL
  target[3] = (vx - vy + w) * VMAX * INVERT[3];   // RR
}

void setup() {
  Serial.begin(115200);
  pinMode(EN, OUTPUT);
  digitalWrite(EN, LOW);
  for (int i = 0; i < 4; i++) M[i]->setMaxSpeed(3000);
  drive(1, 0, 0);                 // start moving forward
  tLast = micros();
  tPhase = millis();
  Serial.println(DEMO ? "DEMO: cycling moves" : "FORWARD (calibrate INVERT[])");
}

void loop() {
#if DEMO
  const char* n[] = {"FORWARD","BACK","STRAFE L","STRAFE R","ROTATE CW","ROTATE CCW","STOP"};
  if (millis() - tPhase > 2500) {
    tPhase = millis();
    switch (phase) {
      case 0: drive( 1, 0, 0); break;
      case 1: drive(-1, 0, 0); break;
      case 2: drive( 0, 1, 0); break;
      case 3: drive( 0,-1, 0); break;
      case 4: drive( 0, 0, 1); break;
      case 5: drive( 0, 0,-1); break;
      case 6: drive( 0, 0, 0); break;
    }
    Serial.println(n[phase]);
    phase = (phase + 1) % 7;
  }
#endif

  // software slew toward target, then pulse — the ramp is what keeps the
  // steppers from stalling and screaming on a speed change.
  unsigned long now = micros();
  float dt = (now - tLast) * 1e-6f;
  tLast = now;
  float lim = ACCEL * dt;
  for (int i = 0; i < 4; i++) {
    float d = target[i] - cur[i];
    if (d >  lim) d =  lim;
    if (d < -lim) d = -lim;
    cur[i] += d;
    M[i]->setSpeed(cur[i]);
    M[i]->runSpeed();
  }
}
