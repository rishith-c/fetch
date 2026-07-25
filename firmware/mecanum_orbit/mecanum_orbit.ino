/*
 * MECANUM ORBIT — the vehicle glides around a circle-ish loop while its FRONT
 * always faces the SAME way (it never rotates). Also tests every mecanum
 * direction: forward, strafe, and the 45-degree diagonals.
 *
 * It's 8 short slides (forward -> fwd-left -> left -> back-left -> back ->
 * back-right -> right -> fwd-right), which close into a loop and repeat.
 *
 * front = Z,A   back = X,Y.   Y-DIR on A2.   Uses your calibrated FWD[].
 * Each slide's wheel signs come straight from mecanum math (+ fwd, - back,
 * 0 = that wheel holds still for a diagonal slide).
 */
const int EN = 8;
//                     X    Y    Z    A
const int STEP[4] = {  2,   3,   4,  12 };
const int DIRP[4] = {  5,  A2,   7,  13 };        // Y dir on A2
bool      FWD [4] = { HIGH, HIGH, HIGH, HIGH };   // X,Y,Z,A forward dir

// corner -> socket (0=X 1=Y 2=Z 3=A).  front=Z,A  back=X,Y
const int FL = 3, FR = 2, RL = 1, RR = 0;   // FL=A FR=Z RL=Y RR=X (vehicle frame)

const int  STEP_US   = 1500;   // slow. lower = faster, raise if it stalls on a slide start
const long LEG_STEPS = 300;    // length of each slide (size of the circle)
const int  PAUSE_MS  = 120;    // tiny settle between slides

// one slide. corner signs: +1 forward, -1 back, 0 = hold that wheel.
void slide(int cFL, int cFR, int cRL, int cRR) {
  int sgn[4]; sgn[FL]=cFL; sgn[FR]=cFR; sgn[RL]=cRL; sgn[RR]=cRR;
  for (int i=0;i<4;i++) if (sgn[i]) digitalWrite(DIRP[i], sgn[i] > 0 ? FWD[i] : !FWD[i]);
  for (long n=0;n<LEG_STEPS;n++) {
    for (int i=0;i<4;i++) if (sgn[i]) digitalWrite(STEP[i], HIGH);
    delayMicroseconds(4);
    for (int i=0;i<4;i++) if (sgn[i]) digitalWrite(STEP[i], LOW);
    delayMicroseconds(STEP_US);
    yield();
  }
  delay(PAUSE_MS);
}

void setup() {
  pinMode(EN, OUTPUT); digitalWrite(EN, LOW);
  for (int i=0;i<4;i++) { pinMode(STEP[i],OUTPUT); pinMode(DIRP[i],OUTPUT); }
}

void loop() {
  //     FL  FR  RL  RR
  slide(+1, +1, +1, +1);   // forward
  slide( 0, +1, +1,  0);   // fwd-left  (diagonal)
  slide(-1, +1, +1, -1);   // left
  slide(-1,  0,  0, -1);   // back-left (diagonal)
  slide(-1, -1, -1, -1);   // backward
  slide( 0, -1, -1,  0);   // back-right(diagonal)
  slide(+1, -1, -1, +1);   // right
  slide(+1,  0,  0, +1);   // fwd-right (diagonal)
  // loop closes back to start -> repeats the orbit
}
