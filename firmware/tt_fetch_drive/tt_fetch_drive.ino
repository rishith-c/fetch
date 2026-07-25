/*
 * FETCH TT PRODUCTION FIRMWARE
 * Arduino Uno R4 + two L298N modules + four TT motors + five HC-SR04.
 *
 * Pi -> Uno (USB CDC, 115200 baud):
 *   V <vx_mm_s> <vy_mm_s> <omega_deg_s>\n
 *   E\n   latch emergency stop
 *   C\n   clear latched emergency stop
 *
 * Uno -> Pi, 10 Hz:
 *   S <front> <left_front> <right_front> <left_rear> <right_rear> <estop>\n
 * Distances are centimetres; 0 means no echo within 2 m. estop is 0 or 1.
 * A 500 ms command watchdog and the local ultrasonic veto stop the motors.
 *
 * MOTOR PIN MAP (remove all four ENA/ENB jumper caps):
 *   M1 PWM D5  IN1 D2   IN2 D4
 *   M2 PWM D6  IN1 D7   IN2 D8
 *   M3 PWM D9  IN1 D12  IN2 D13
 *   M4 PWM D10 IN1 A0   IN2 A1
 *
 * SONAR PIN MAP:
 *   all five TRIG -> D3
 *   front ECHO D11; left-front A2; right-front A3;
 *   left-rear A4; right-rear A5
 *
 * The shared trigger is a pin-count compromise forced by direct L298N control.
 * All echo pulses are captured concurrently (never sequential blocking reads).
 * Every module is triggered once per 65 ms, satisfying the HC-SR04 >60 ms
 * repeat-cycle guidance. Physical cross-talk testing is still mandatory.
 */

#include <Arduino.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

const uint8_t PWM_PIN[4] = {5, 6, 9, 10};
const uint8_t IN1_PIN[4] = {2, 7, 12, A0};
const uint8_t IN2_PIN[4] = {4, 8, 13, A1};

// CORNER[FL, FR, RL, RR] gives the M1..M4 index at that corner.
const uint8_t CORNER[4] = {0, 1, 2, 3};
// Change a sign only after the one-wheel commissioning test.
const int8_t POLARITY[4] = {+1, +1, +1, +1};
const float TRIM[4] = {1.00f, 1.00f, 1.00f, 1.00f};

const uint8_t TRIG_PIN = 3;
const uint8_t ECHO_PIN[5] = {11, A2, A3, A4, A5};
enum SonarIndex { FRONT = 0, LEFT_FRONT = 1, RIGHT_FRONT = 2,
                  LEFT_REAR = 3, RIGHT_REAR = 4 };

const float MAX_LINEAR_MM_S = 250.0f;
const float MAX_OMEGA_DEG_S = 120.0f;
const int MIN_MOVING_PWM = 68;
const uint32_t COMMAND_WATCHDOG_MS = 500;
const uint32_t SONAR_PERIOD_MS = 65;
const uint32_t SONAR_TIMEOUT_US = 12000;  // about 2.0 m round trip
const uint32_t MOTOR_TICK_MS = 10;
const int PWM_SLEW_PER_TICK = 6;          // ~0.43 s from 0 to full

const int FRONT_STOP_CM = 60;
const int SIDE_STOP_CM = 35;
const int ROTATE_STOP_CM = 20;

int targetPwm[4] = {0, 0, 0, 0};
int actualPwm[4] = {0, 0, 0, 0};
int sonarCm[5] = {0, 0, 0, 0, 0};
uint16_t sonarHistory[5][3] = {};
uint8_t sonarHistoryCount[5] = {0, 0, 0, 0, 0};
uint8_t sonarHistoryPos[5] = {0, 0, 0, 0, 0};
uint8_t completedSonarFrames = 0;

float requestedVx = 0.0f;
float requestedVy = 0.0f;
float requestedOmega = 0.0f;
bool obstacleStop = true;   // motion remains inhibited through startup samples
bool latchedEstop = false;
bool velocityMode = false;

uint32_t lastCommandMs = 0;
uint32_t lastSonarMs = 0;
uint32_t lastReportMs = 0;
uint32_t lastMotorTickMs = 0;

char lineBuffer[64];
uint8_t lineLength = 0;

static int moveToward(int value, int target, int amount) {
  if (value < target) return min(value + amount, target);
  if (value > target) return max(value - amount, target);
  return value;
}

static int medianOfAvailable(uint16_t *values, uint8_t count) {
  uint16_t v[3] = {201, 201, 201};
  for (uint8_t i = 0; i < count; ++i) v[i] = values[i];
  for (uint8_t i = 0; i < count; ++i) {
    for (uint8_t j = i + 1; j < count; ++j) {
      if (v[j] < v[i]) { uint16_t t = v[i]; v[i] = v[j]; v[j] = t; }
    }
  }
  return v[count / 2];
}

static bool nearObstacle(uint8_t index, int thresholdCm) {
  return sonarCm[index] > 0 && sonarCm[index] <= thresholdCm;
}

static bool blockedFor(float vx, float vy, float omega) {
  if (completedSonarFrames < 3) return true;
  if (vx > 5.0f && nearObstacle(FRONT, FRONT_STOP_CM)) return true;
  if (vx < -5.0f && (nearObstacle(LEFT_REAR, SIDE_STOP_CM) ||
                     nearObstacle(RIGHT_REAR, SIDE_STOP_CM))) return true;
  if (vy < -5.0f && (nearObstacle(LEFT_FRONT, SIDE_STOP_CM) ||
                     nearObstacle(LEFT_REAR, SIDE_STOP_CM))) return true;
  if (vy > 5.0f && (nearObstacle(RIGHT_FRONT, SIDE_STOP_CM) ||
                    nearObstacle(RIGHT_REAR, SIDE_STOP_CM))) return true;
  if (fabsf(omega) > 5.0f &&
      (nearObstacle(FRONT, ROTATE_STOP_CM) ||
       nearObstacle(LEFT_FRONT, ROTATE_STOP_CM) ||
       nearObstacle(RIGHT_FRONT, ROTATE_STOP_CM) ||
       nearObstacle(LEFT_REAR, ROTATE_STOP_CM) ||
       nearObstacle(RIGHT_REAR, ROTATE_STOP_CM))) return true;
  return false;
}

static int normalizedToPwm(float value, uint8_t motorIndex) {
  float magnitude = fabsf(value) * TRIM[motorIndex];
  if (magnitude < 0.02f) return 0;
  magnitude = constrain(magnitude, 0.0f, 1.0f);
  int pwm = MIN_MOVING_PWM + (int)lroundf(magnitude * (255 - MIN_MOVING_PWM));
  return value < 0.0f ? -pwm : pwm;
}

static void stopTargets() {
  for (uint8_t i = 0; i < 4; ++i) targetPwm[i] = 0;
}

static void setVelocity(float vxMmS, float vyMmS, float omegaDegS) {
  requestedVx = constrain(vxMmS, -MAX_LINEAR_MM_S, MAX_LINEAR_MM_S);
  requestedVy = constrain(vyMmS, -MAX_LINEAR_MM_S, MAX_LINEAR_MM_S);
  requestedOmega = constrain(omegaDegS, -MAX_OMEGA_DEG_S, MAX_OMEGA_DEG_S);
  obstacleStop = blockedFor(requestedVx, requestedVy, requestedOmega);
  if (latchedEstop || obstacleStop) {
    stopTargets();
    return;
  }

  float x = requestedVx / MAX_LINEAR_MM_S;
  float y = requestedVy / MAX_LINEAR_MM_S;
  float w = requestedOmega / MAX_OMEGA_DEG_S;
  float wheel[4] = {
    x - y - w,  // front-left
    x + y + w,  // front-right
    x + y - w,  // rear-left
    x - y + w   // rear-right
  };
  float maximum = 1.0f;
  for (uint8_t i = 0; i < 4; ++i) maximum = max(maximum, fabsf(wheel[i]));
  for (uint8_t corner = 0; corner < 4; ++corner) {
    uint8_t motor = CORNER[corner];
    targetPwm[motor] = normalizedToPwm(wheel[corner] / maximum, motor);
  }
}

static void writeMotor(uint8_t motor, int pwm) {
  pwm = constrain(pwm * POLARITY[motor], -255, 255);
  if (pwm == 0) {
    analogWrite(PWM_PIN[motor], 0);
    digitalWrite(IN1_PIN[motor], LOW);
    digitalWrite(IN2_PIN[motor], LOW);
    return;
  }
  digitalWrite(IN1_PIN[motor], pwm > 0 ? HIGH : LOW);
  digitalWrite(IN2_PIN[motor], pwm > 0 ? LOW : HIGH);
  analogWrite(PWM_PIN[motor], abs(pwm));
}

static void serviceMotors() {
  uint32_t now = millis();
  if (now - lastMotorTickMs < MOTOR_TICK_MS) return;
  lastMotorTickMs = now;
  for (uint8_t i = 0; i < 4; ++i) {
    actualPwm[i] = moveToward(actualPwm[i], targetPwm[i], PWM_SLEW_PER_TICK);
    writeMotor(i, actualPwm[i]);
  }
}

static void storeSonarReading(uint8_t sensor, uint32_t pulseWidthUs) {
  uint16_t cm = pulseWidthUs ? (uint16_t)(pulseWidthUs / 58UL) : 201;
  if (cm < 2 || cm > 200) cm = 201;
  sonarHistory[sensor][sonarHistoryPos[sensor]] = cm;
  sonarHistoryPos[sensor] = (sonarHistoryPos[sensor] + 1) % 3;
  if (sonarHistoryCount[sensor] < 3) ++sonarHistoryCount[sensor];
  int filtered = medianOfAvailable(sonarHistory[sensor], sonarHistoryCount[sensor]);
  sonarCm[sensor] = filtered > 200 ? 0 : filtered;
}

static void sampleAllSonars() {
  // All sensors transmit together because they share TRIG. Their ECHO pulses
  // must therefore be measured together; sequential blocking reads are wrong.
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(4);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  bool highSeen[5] = {false, false, false, false, false};
  bool finished[5] = {false, false, false, false, false};
  uint32_t riseUs[5] = {0, 0, 0, 0, 0};
  uint32_t pulseUs[5] = {0, 0, 0, 0, 0};
  uint32_t beganUs = micros();

  while ((uint32_t)(micros() - beganUs) < SONAR_TIMEOUT_US) {
    uint32_t nowUs = micros();
    for (uint8_t i = 0; i < 5; ++i) {
      if (finished[i]) continue;
      bool high = digitalRead(ECHO_PIN[i]) == HIGH;
      if (!highSeen[i] && high) {
        highSeen[i] = true;
        riseUs[i] = nowUs;
      } else if (highSeen[i] && !high) {
        pulseUs[i] = (uint32_t)(nowUs - riseUs[i]);
        finished[i] = true;
      }
    }
  }

  for (uint8_t i = 0; i < 5; ++i) storeSonarReading(i, pulseUs[i]);
  if (completedSonarFrames < 255) ++completedSonarFrames;

  obstacleStop = blockedFor(requestedVx, requestedVy, requestedOmega);
  if (latchedEstop || obstacleStop) stopTargets();
}

static void reportTelemetry() {
  Serial.print("S");
  for (uint8_t i = 0; i < 5; ++i) {
    Serial.print(' ');
    Serial.print(sonarCm[i]);
  }
  Serial.print(' ');
  Serial.println((latchedEstop || obstacleStop) ? 1 : 0);
}

static void handleLine(char *line) {
  while (*line == ' ' || *line == '\t') ++line;
  if (*line == '\0') return;

  if (line[0] == 'E' || line[0] == 'e') {
    latchedEstop = true;
    velocityMode = false;
    stopTargets();
    return;
  }
  if (line[0] == 'C' || line[0] == 'c') {
    latchedEstop = false;
    setVelocity(0, 0, 0);
    return;
  }

  float vx, vy, omega;
  if ((line[0] == 'V' || line[0] == 'v') &&
      sscanf(line + 1, "%f %f %f", &vx, &vy, &omega) == 3) {
    lastCommandMs = millis();
    velocityMode = true;
    setVelocity(vx, vy, omega);
    return;
  }

  // Bench controls; production navigation uses V commands.
  const float speed = 120.0f;
  if      (line[0] == 'f') setVelocity(+speed, 0, 0);
  else if (line[0] == 'b') setVelocity(-speed, 0, 0);
  else if (line[0] == 'l') setVelocity(0, -speed, 0);
  else if (line[0] == 'r') setVelocity(0, +speed, 0);
  else if (line[0] == 'q') setVelocity(0, 0, -60);
  else if (line[0] == 'w') setVelocity(0, 0, +60);
  else if (line[0] == 's') setVelocity(0, 0, 0);
  else return;
  lastCommandMs = millis();
  velocityMode = true;
}

static void serviceSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      lineBuffer[lineLength] = '\0';
      handleLine(lineBuffer);
      lineLength = 0;
    } else if (lineLength < sizeof(lineBuffer) - 1) {
      lineBuffer[lineLength++] = c;
    } else {
      lineLength = 0;  // reject an overlong command instead of parsing a tail
    }
  }
}

void setup() {
  Serial.begin(115200);
  for (uint8_t i = 0; i < 4; ++i) {
    pinMode(PWM_PIN[i], OUTPUT);
    pinMode(IN1_PIN[i], OUTPUT);
    pinMode(IN2_PIN[i], OUTPUT);
    writeMotor(i, 0);
  }
  pinMode(TRIG_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);
  for (uint8_t i = 0; i < 5; ++i) pinMode(ECHO_PIN[i], INPUT);
  lastCommandMs = millis();
  Serial.println("FETCH_TT_READY V3");
}

void loop() {
  serviceSerial();
  uint32_t now = millis();

  if (velocityMode && now - lastCommandMs > COMMAND_WATCHDOG_MS) {
    velocityMode = false;
    requestedVx = requestedVy = requestedOmega = 0;
    stopTargets();
  }
  if (now - lastSonarMs >= SONAR_PERIOD_MS) {
    lastSonarMs = now;
    sampleAllSonars();
  }
  if (now - lastReportMs >= 100) {
    lastReportMs = now;
    reportTelemetry();
  }
  serviceMotors();
  yield();
}
