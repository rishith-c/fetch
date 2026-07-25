/*
 * MECANUM TURN 90 — rotates in place, pauses, repeats.
 * front = Z,A   back = X,Y.   Y-DIR on A2.   Uses your calibrated FWD[].
 *
 * Rotation = LEFT wheels one way + RIGHT wheels the other (spins in place).
 * TUNE TURN_STEPS until each spin is exactly 90 degrees (open-loop, by eye).
 * If it turns the WRONG way, flip the signs in the move() call at the bottom.
 */
const int EN = 8;
//                     X    Y    Z    A
const int STEP[4] = {  2,   3,   4,  12 };
const int DIRP[4] = {  5,  A2,   7,  13 };        // Y dir on A2
bool      FWD [4] = { HIGH, HIGH, HIGH, HIGH };   // X,Y,Z,A forward dir (from your test)

// corner -> socket (0=X 1=Y 2=Z 3=A).  front=Z,A  back=X,Y
const int FL = 3, FR = 2, RL = 1, RR = 0;   // FL=A FR=Z RL=Y RR=X (vehicle frame)

const int  STEP_US    = 1200;   // speed (raise if it stalls)
const long TURN_STEPS = 300;    // <-- TUNE until the spin is exactly 90 degrees

void move(int fl, int fr, int rl, int rr, long steps) {
  int s[4] = {0,0,0,0};
  s[FL]=fl; s[FR]=fr; s[RL]=rl; s[RR]=rr;
  for (int i=0;i<4;i++) digitalWrite(DIRP[i], s[i] > 0 ? FWD[i] : !FWD[i]);
  for (long n=0;n<steps;n++) {
    for (int i=0;i<4;i++) digitalWrite(STEP[i], HIGH);
    delayMicroseconds(4);
    for (int i=0;i<4;i++) digitalWrite(STEP[i], LOW);
    delayMicroseconds(STEP_US);
  }
}

void setup() {
  pinMode(EN, OUTPUT); digitalWrite(EN, LOW);
  for (int i=0;i<4;i++) { pinMode(STEP[i],OUTPUT); pinMode(DIRP[i],OUTPUT); }
}

void loop() {
  // left wheels forward, right wheels back -> spins clockwise (turn right)
  move(+1, -1, +1, -1, TURN_STEPS);
  delay(1500);                 // pause so you can see each 90
}
