#include <AccelStepper.h>

// ---------------- SOCKET WIRING (don't touch) ----------------
// socket:      X        Y        Z        A
// step/dir:   2,5      3,6      4,7     12,13
AccelStepper MX(AccelStepper::DRIVER, 2, 5);
AccelStepper MY(AccelStepper::DRIVER, 3, 6);
AccelStepper MZ(AccelStepper::DRIVER, 4, 7);
AccelStepper MA(AccelStepper::DRIVER, 12, 13);
AccelStepper* SOCKET[4] = { &MX, &MY, &MZ, &MA };

// ---------------- THE ONE LINE THAT FIXES STRAFE ----------------
// Which SOCKET (0=X 1=Y 2=Z 3=A) sits at each CORNER {FL, FR, RL, RR}.
// Your old code assumed {0,1,2,3}. Since fwd/back/rotate work but strafe
// doesn't, front/rear are swapped somewhere. Try these in order:
//   {2,3,0,1}  <- both sides front/rear swapped (start here)
//   {2,1,0,3}  <- left side swapped only
//   {0,3,2,1}  <- right side swapped only
//   {0,1,2,3}  <- original (strafe fails = not this one)
int CORNER[4] = { 2, 3, 0, 1 };

#define ENABLE_PIN 8
const float MAX_SPEED = 150;
const float ACCEL = 50;

void setup() {
  pinMode(ENABLE_PIN, OUTPUT);
  digitalWrite(ENABLE_PIN, LOW);
  for (int i = 0; i < 4; i++) {
    SOCKET[i]->setMaxSpeed(MAX_SPEED);
    SOCKET[i]->setAcceleration(ACCEL);
  }

  // BOOT SELF-TEST: pulses corners in order FL, FR, RL, RR.
  // If the pulses don't go front-left, front-right, rear-left, rear-right,
  // pick the next CORNER preset above and re-upload.
  delay(2000);
  long p[4];
  for (int c = 0; c < 4; c++) {
    for (int i = 0; i < 4; i++) p[i] = 0;
    p[c] = 400;
    moveRobot(p[0], p[1], p[2], p[3]);
    delay(700);
  }
  delay(2000);
}

// cmd order is ALWAYS {FL, FR, RL, RR}; CORNER[] routes to the right socket
void moveRobot(long fl, long fr, long rl, long rr) {
  long cmd[4] = { fl, fr, rl, rr };
  for (int c = 0; c < 4; c++) SOCKET[CORNER[c]]->move(cmd[c]);
  bool busy = true;
  while (busy) {
    busy = false;
    for (int i = 0; i < 4; i++) {
      if (SOCKET[i]->distanceToGo() != 0) busy = true;
      SOCKET[i]->run();
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

void loop() {
  strafeLeft(800);
  strafeRight(800);
  delay(1000);
}