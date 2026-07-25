// Y DIRECTION JUMPER TEST — isolates just the Y motor + its A2 dir jumper.
// Steps Y continuously and FLIPS its direction every 2 seconds.
//
// WATCH ONLY THE Y MOTOR:
//   - reverses direction every 2s  -> the A2 jumper WORKS, dir is controllable
//   - keeps spinning ONE way       -> the A2->DIR jumper is NOT connected right
//
// dirY is on A2 (the "Resume" pin), jumpered to the Y driver's DIR pin.

const int enablePin = 8;
const int stepY = 3;
const int dirY  = A2;

unsigned long tFlip = 0;
bool dir = false;

void setup() {
  pinMode(enablePin, OUTPUT);
  digitalWrite(enablePin, LOW);      // drivers on
  pinMode(stepY, OUTPUT);
  pinMode(dirY, OUTPUT);
  digitalWrite(dirY, dir);
}

void loop() {
  if (millis() - tFlip > 2000) {     // flip direction every 2 seconds
    dir = !dir;
    digitalWrite(dirY, dir);
    tFlip = millis();
  }
  digitalWrite(stepY, HIGH);
  delayMicroseconds(800);
  digitalWrite(stepY, LOW);
  delayMicroseconds(800);
}
