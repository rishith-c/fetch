/*
 * MECANUM FLOW — one SMOOTH, CONTINUOUS demo that glides through every move:
 *   forward -> diagonal -> strafe -> spin -> arc -> strafe -> ease out -> loop
 * No stops, no choppy legs. It morphs the velocity vector (vx,vy,w) with
 * smoothstep easing, so it flows.
 *
 * This is a REAL mecanum driver: setVel(vx, vy, w) drives all 4 wheels at the
 * right speed AND direction. vx=forward, vy=left, w=spin(CCW). Everything else
 * is just a choreography of (vx,vy,w) over time.
 *
 * front = A,Z   back = Y,X.   Y-DIR on A2.   Uses your calibrated FWD[].
 */
const int EN = 8;
//                     X    Y    Z    A
const int STEP[4] = {  2,   3,   4,  12 };
const int DIRP[4] = {  5,  A2,   7,  13 };        // Y dir on A2
bool      FWD [4] = { HIGH, HIGH, HIGH, HIGH };   // X,Y,Z,A forward dir
const int FL = 3, FR = 2, RL = 1, RR = 0;         // FL=A FR=Z RL=Y RR=X (vehicle frame)

const int   MAX_US = 900;    // wheel interval at full speed (smaller=faster; raise if it stalls)
const float MINSP  = 0.04;   // below this a wheel holds

float target[4];             // signed wheel speed by socket, -1..1
unsigned long nextStep[4];
int dirNow[4] = { -1, -1, -1, -1 };

// mecanum kinematics + keep-in-range normalization
void setVel(float vx, float vy, float w) {
  float s[4];
  s[FL] = vx - vy - w;
  s[FR] = vx + vy + w;
  s[RL] = vx + vy - w;
  s[RR] = vx - vy + w;
  float mx = 1.0;
  for (int i=0;i<4;i++) if (fabs(s[i]) > mx) mx = fabs(s[i]);
  for (int i=0;i<4;i++) target[i] = s[i] / mx;     // scale together (keeps the direction true)
}

// choreography: velocity keyframes {vx, vy, w, seconds-to-morph-into-it}
struct KF { float vx, vy, w, sec; };
KF seq[] = {
  { 0.8,  0.0, 0.0, 2.5 },   // forward
  { 0.6, -0.6, 0.0, 2.5 },   // diagonal front-right
  { 0.0, -0.8, 0.0, 2.5 },   // strafe right
  { 0.0,  0.0, 0.7, 3.0 },   // spin in place
  { 0.6,  0.0, 0.5, 3.5 },   // arc (forward + turn)
  { 0.0,  0.8, 0.0, 2.5 },   // strafe left
  { 0.0,  0.0, 0.0, 1.2 },   // ease to a stop, then loop
};
const int NKF = sizeof(seq) / sizeof(seq[0]);

float smoothstep(float a) { return a*a*(3.0 - 2.0*a); }

unsigned long t0;

void setup() {
  pinMode(EN, OUTPUT); digitalWrite(EN, LOW);
  for (int i=0;i<4;i++) { pinMode(STEP[i], OUTPUT); pinMode(DIRP[i], OUTPUT); }
  t0 = micros();
  for (int i=0;i<4;i++) nextStep[i] = micros();
}

void loop() {
  unsigned long now = micros();

  // ---- work out the current (vx,vy,w) by morphing between keyframes ----
  float total = 0; for (int i=0;i<NKF;i++) total += seq[i].sec;
  float tc = fmod((now - t0) / 1e6, total);
  float acc = 0; int idx = 0;
  for (idx=0; idx<NKF; idx++) { if (tc < acc + seq[idx].sec) break; acc += seq[idx].sec; }
  if (idx >= NKF) idx = NKF - 1;
  int p = (idx - 1 + NKF) % NKF;
  float f = smoothstep((tc - acc) / seq[idx].sec);
  float vx = seq[p].vx + (seq[idx].vx - seq[p].vx) * f;
  float vy = seq[p].vy + (seq[idx].vy - seq[p].vy) * f;
  float w  = seq[p].w  + (seq[idx].w  - seq[p].w ) * f;
  setVel(vx, vy, w);

  // ---- step each wheel at its own rate/direction ----
  for (int i=0;i<4;i++) {
    float s = target[i];
    int dir = (s >= 0) ? FWD[i] : !FWD[i];
    if (dir != dirNow[i]) { digitalWrite(DIRP[i], dir); dirNow[i] = dir; }
    float mag = fabs(s);
    if (mag < MINSP) { nextStep[i] = now; continue; }
    if ((long)(now - nextStep[i]) >= 0) {
      digitalWrite(STEP[i], HIGH); delayMicroseconds(3); digitalWrite(STEP[i], LOW);
      nextStep[i] = now + (unsigned long)(MAX_US / mag);
    }
  }
  yield();
}