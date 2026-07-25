/*
 * SQUARE by turning — forward, turn 90 right, forward, turn 90 right...
 * front = Z,A   back = X,Y.  Y-DIR on A2.  Uses your calibrated FWD[].
 *
 * TUNE TURN_STEPS until each turn is ~90 degrees (open-loop, so it's by eye).
 */
const int EN = 8;
//                     X    Y    Z    A
const int STEP[4] = {  2,   3,   4,  12 };
const int DIRP[4] = {  5,  A2,   7,  13 };        // Y dir on A2
bool      FWD [4] = { HIGH, HIGH, HIGH, HIGH };   // X,Y,Z,A forward dir (from your test)

// corner -> socket (0=X 1=Y 2=Z 3=A).  front=Z,A  back=X,Y
const int FL = 3, FR = 2, RL = 1, RR = 0;   // FL=A FR=Z RL=Y RR=X (vehicle frame)

const int  STEP_US    = 1200;   // speed (raise if it stalls)
const long FWD_STEPS  = 600;    // length of each side
const long TURN_STEPS = 300;    // <-- TUNE until a turn is ~90 degrees

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
  delay(400);
}

void setup() {
  pinMode(EN, OUTPUT); digitalWrite(EN, LOW);
  for (int i=0;i<4;i++) { pinMode(STEP[i],OUTPUT); pinMode(DIRP[i],OUTPUT); }
}

void loop() {
  move(+1, +1, +1, +1, FWD_STEPS);   // forward
  move(+1, -1, +1, -1, TURN_STEPS);  // turn 90 right (left wheels fwd, right wheels back)
  // 4 loops = one full square
}
