/*
 * MECANUM CIRCLE — drives a smooth circle (forward, one side faster).
 * front = Z,A   back = X,Y.   Y-DIR on A2.   Uses your calibrated FWD[].
 *
 * All 4 wheels roll FORWARD; the LEFT side runs slower and the RIGHT side
 * faster, so it curves left in a circle. Each wheel has its own step rate,
 * so this steps them independently (not all together like the other tests).
 *
 * TUNE: bring INNER_US and OUTER_US closer -> BIGGER circle.
 *       further apart -> TIGHTER circle.  equal -> straight line.
 */
const int EN = 8;
//                     X    Y    Z    A
const int STEP[4] = {  2,   3,   4,  12 };
const int DIRP[4] = {  5,  A2,   7,  13 };        // Y dir on A2
bool      FWD [4] = { HIGH, HIGH, HIGH, HIGH };   // X,Y,Z,A forward dir (from your test)

// corner -> socket (0=X 1=Y 2=Z 3=A).  front=Z,A  back=X,Y
const int FL = 3, FR = 2, RL = 1, RR = 0;   // FL=A FR=Z RL=Y RR=X (vehicle frame)

const int INNER_US = 5000;   // slower side (inner of the circle) — SLOW
const int OUTER_US = 3000;   // faster side (outer of the circle) — SLOW

int interval[4];
unsigned long nextStep[4];

void setup() {
  pinMode(EN, OUTPUT); digitalWrite(EN, LOW);
  for (int i=0;i<4;i++) {
    pinMode(STEP[i], OUTPUT); pinMode(DIRP[i], OUTPUT);
    digitalWrite(DIRP[i], FWD[i]);            // all wheels forward
  }
  // LEFT side slow, RIGHT side fast -> curves LEFT
  interval[FL] = INNER_US; interval[RL] = INNER_US;   // left  (inner)
  interval[FR] = OUTER_US; interval[RR] = OUTER_US;   // right (outer)
  unsigned long now = micros();
  for (int i=0;i<4;i++) nextStep[i] = now;
}

void loop() {
  unsigned long now = micros();
  for (int i=0;i<4;i++) {
    if ((long)(now - nextStep[i]) >= 0) {     // this wheel's step is due
      digitalWrite(STEP[i], HIGH);
      delayMicroseconds(3);
      digitalWrite(STEP[i], LOW);
      nextStep[i] += interval[i];
    }
  }
}
