/*
 * MECANUM SIDEWAYS FIX — CNC Shield V3 + 4x A4988 + Uno R4.
 *
 * WHY YOUR VERSION COULDN'T STRAFE:
 *   FR was on DIR pin 6 — the Y socket's DIR trace is DEAD on this shield.
 *   Strafing needs FR+RL reversed; FR could never reverse. Fixed: FR dir = A2
 *   (the jumper wire from the "Resume" pin to the bent-out driver DIR pin).
 *
 * CALIBRATE (2 minutes, wheels off the ground, Serial Monitor 115200):
 *   1) press '1' '2' '3' '4' — each spins ONE motor. For each, note which
 *      corner moves and whether the wheel rolls robot-FORWARD.
 *   2) corner wrong? edit the socket->corner order in the constructors below.
 *      rolls backward? flip that motor's entry in POL[] (+1 <-> -1).
 *   3) re-upload once. Then f b l r q e all work. 'w' runs the full demo.
 */
#include <AccelStepper.h>

// socket -> corner (EDIT AFTER STEP 1 IF NEEDED). dir pins: X=5 Y=A2 Z=7 A=13
AccelStepper FL(AccelStepper::DRIVER, 2, 5);    // X socket
AccelStepper FR(AccelStepper::DRIVER, 3, A2);   // Y socket — A2, NEVER 6!
AccelStepper RL(AccelStepper::DRIVER, 4, 7);    // Z socket
AccelStepper RR(AccelStepper::DRIVER, 12, 13);  // A socket

// +1 if '1'..'4' made that wheel roll robot-forward, -1 if it rolled backward.
// Left and right sides are mirror-mounted, so two of these are usually -1.
int POL[4] = { +1, -1, +1, -1 };                // FL, FR, RL, RR — EDIT IN STEP 2

#define ENABLE_PIN 8
const float MAX_SPEED = 150;
const float ACCEL = 50;

AccelStepper* M[4] = { &FL, &FR, &RL, &RR };

void setup() {
  Serial.begin(115200);
  pinMode(ENABLE_PIN, OUTPUT);
  digitalWrite(ENABLE_PIN, LOW);
  for (int i = 0; i < 4; i++) {
    M[i]->setMaxSpeed(MAX_SPEED);
    M[i]->setAcceleration(ACCEL);
  }
  Serial.println("READY. 1-4=test one motor | f b l r q e = move | w = demo");
}

void moveRobot(long fl, long fr, long rl, long rr) {
  long cmd[4] = { fl, fr, rl, rr };
  for (int i = 0; i < 4; i++) M[i]->move(cmd[i] * POL[i]);
  bool busy = true;
  while (busy) {
    busy = false;
    for (int i = 0; i < 4; i++) {
      if (M[i]->distanceToGo() != 0) busy = true;
      M[i]->run();
    }
    if (Serial.available() && Serial.peek() == 's') {   // emergency stop
      Serial.read();
      for (int i = 0; i < 4; i++) M[i]->stop();
    }
    yield();
  }
  delay(300);
}

void forward(long s)      { moveRobot( s,  s,  s,  s); }
void backward(long s)     { moveRobot(-s, -s, -s, -s); }
void strafeLeft(long s)   { moveRobot(-s,  s,  s, -s); }
void strafeRight(long s)  { moveRobot( s, -s, -s,  s); }
void rotateLeft(long s)   { moveRobot(-s,  s, -s,  s); }
void rotateRight(long s)  { moveRobot( s, -s,  s, -s); }
void diagFL(long s)       { moveRobot( 0,  s,  s,  0); }
void diagFR(long s)       { moveRobot( s,  0,  0,  s); }
void diagBL(long s)       { moveRobot(-s,  0,  0, -s); }
void diagBR(long s)       { moveRobot( 0, -s, -s,  0); }

void testOne(int i) {
  const char* NAME[4] = { "FL(X)", "FR(Y)", "RL(Z)", "RR(A)" };
  Serial.print("spinning "); Serial.print(NAME[i]);
  Serial.println("  -> should roll robot-FORWARD. wrong corner? reorder ctors."
                 " wrong way? flip POL.");
  long cmd[4] = { 0, 0, 0, 0 };
  cmd[i] = 800;
  moveRobot(cmd[0], cmd[1], cmd[2], cmd[3]);
}

void demo() {
  forward(800);     backward(800);
  strafeLeft(800);  strafeRight(800);
  rotateLeft(800);  rotateRight(800);
  diagFL(800);      diagFR(800);
  diagBL(800);      diagBR(800);
}

void loop() {
  if (Serial.available()) {
    char c = tolower(Serial.read());
    if (c >= '1' && c <= '4') testOne(c - '1');
    else if (c == 'f') forward(800);
    else if (c == 'b') backward(800);
    else if (c == 'l') strafeLeft(800);
    else if (c == 'r') strafeRight(800);
    else if (c == 'q') rotateLeft(800);
    else if (c == 'e') rotateRight(800);
    else if (c == 'w') demo();
  }
  yield();
}
