/*
 * MECANUM CRAB-CIRCLE — traces a circle while the FRONT keeps facing forward.
 * Pure translation (no turning): the slide-direction sweeps 360 deg, so the
 * robot's center goes in a circle but the body never rotates.
 *
 * front = Z,A   back = X,Y.   Y-DIR on A2.   Uses your calibrated FWD[].
 *
 * How: mecanum translation splits into two DIAGONAL pairs whose speeds are
 *   d1 = vx - vy  (front-left + rear-right)
 *   d2 = vx + vy  (front-right + rear-left)
 * With vx=cos(t), vy=sin(t) sweeping, each diagonal speeds up, slows, and
 * REVERSES twice per circle — that's the crab motion. Wheels reverse while
 * near-stopped, so it's smooth.
 */
const int EN = 8;
//                     X    Y    Z    A
const int STEP[4] = {  2,   3,   4,  12 };
const int DIRP[4] = {  5,  A2,   7,  13 };        // Y dir on A2
bool      FWD [4] = { HIGH, HIGH, HIGH, HIGH };   // X,Y,Z,A forward dir

// corner -> socket (0=X 1=Y 2=Z 3=A).  front=Z,A  back=X,Y
const int FL = 3, FR = 2, RL = 1, RR = 0;   // FL=A FR=Z RL=Y RR=X (vehicle frame)

const float CIRCLE_SECONDS = 12.0;   // seconds for one full circle (bigger = slower)
const int   BASE_US        = 1200;   // wheel interval at full speed (smaller = faster; raise if it stalls)
const float MIN_SPEED      = 0.05;   // below this a wheel just holds

float sp[4];
unsigned long nextStep[4];
int dirNow[4] = { -1, -1, -1, -1 };
unsigned long t0;

void setup() {
  pinMode(EN, OUTPUT); digitalWrite(EN, LOW);
  for (int i = 0; i < 4; i++) { pinMode(STEP[i], OUTPUT); pinMode(DIRP[i], OUTPUT); }
  t0 = micros();
  for (int i = 0; i < 4; i++) nextStep[i] = micros();
}

void loop() {
  unsigned long now = micros();
  float th = 2.0 * PI * ((now - t0) / 1e6) / CIRCLE_SECONDS;   // slide direction
  float vx = cos(th), vy = sin(th);
  float d1 = vx - vy, d2 = vx + vy;
  sp[FL] = d1; sp[RR] = d1;      // one diagonal
  sp[FR] = d2; sp[RL] = d2;      // other diagonal

  for (int i = 0; i < 4; i++) {
    float s = sp[i];
    int dir = (s >= 0) ? FWD[i] : !FWD[i];
    if (dir != dirNow[i]) { digitalWrite(DIRP[i], dir); dirNow[i] = dir; }
    float mag = fabs(s);
    if (mag < MIN_SPEED) { nextStep[i] = now; continue; }   // ~stopped
    if ((long)(now - nextStep[i]) >= 0) {
      digitalWrite(STEP[i], HIGH); delayMicroseconds(3); digitalWrite(STEP[i], LOW);
      nextStep[i] = now + (unsigned long)(BASE_US / mag);
    }
  }
  yield();
}
