// CNC Shield V3 — all 4 motors spin the same direction.
// UNO R4 + 4x A4988 (R100, Vref 1.02V) + 4x NEMA17.
// Y is flipped (LOW) because its coil was wired reversed.

const int enablePin = 8;

const int stepX = 2;  const int dirX = 5;
const int stepY = 3;  const int dirY = A5;
const int stepZ = 4;  const int dirZ = 7;
const int stepA = 12; const int dirA = 13;

void setup() {
  // Activate shield drivers
  pinMode(enablePin, OUTPUT);
  digitalWrite(enablePin, LOW);

  // Set motor pins as outputs
  pinMode(stepX, OUTPUT); pinMode(dirX, OUTPUT);
  pinMode(stepY, OUTPUT); pinMode(dirY, OUTPUT);
  pinMode(stepZ, OUTPUT); pinMode(dirZ, OUTPUT);
  pinMode(stepA, OUTPUT); pinMode(dirA, OUTPUT);

  // All wired the same now -> all the same direction
  digitalWrite(dirX, LOW);
  digitalWrite(dirY, LOW);   // back to HIGH: the rewire already reversed Y
  digitalWrite(dirZ, LOW);
  digitalWrite(dirA, LOW);
}

void loop() {
  // Step all four at once
  digitalWrite(stepX, HIGH);
  digitalWrite(stepY, HIGH);
  digitalWrite(stepZ, HIGH);
  digitalWrite(stepA, HIGH);
  delayMicroseconds(600);   // lower = faster

  digitalWrite(stepX, LOW);
  digitalWrite(stepY, LOW);
  digitalWrite(stepZ, LOW);
  digitalWrite(stepA, LOW);
  delayMicroseconds(600);
}