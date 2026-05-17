#include <Wire.h>
#include "FS.h"
#include "SPIFFS.h"

#define IMU_ADDRESS   0x68
#define WHO_AM_I_REG  0x75
#define PWR_MGMT0_REG 0x1F
#define SLEEP_BIT     0x80  // Bit 7 in PWR_MGMT0

#define ACCEL_DATA_START 0x0B  // Start register for accel + gyro data

// Timing constants
const unsigned long SLEEP_DURATION_MS = 60UL * 1000UL;  // 1 minute
const unsigned long ACTIVE_DURATION_MS = 60UL * 1000UL; // 1 minute
const int TOTAL_CYCLES = 2;
const unsigned long LOG_INTERVAL_MS = 25; // Data sampling every 25ms

// Data structure for a single IMU log entry
struct LogEntry {
  unsigned long timestamp;
  int16_t ax, ay, az;
  int16_t gx, gy, gz;
  int cycle;
  bool activeMode;  // true = active, false = sleep
};

// Max samples per active period: 60,000 / 25 = 2400 per active period
// Total max samples = 2400 * TOTAL_CYCLES
// Adjust if memory is constrained
const int MAX_SAMPLES = 2400 * TOTAL_CYCLES;
LogEntry logBuffer[MAX_SAMPLES];
int logIndex = 0;

// I2C helper functions
byte readI2CByte(byte reg) {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(IMU_ADDRESS, 1);
  return Wire.read();
}

void writeI2CByte(byte reg, byte val) {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

// Wake IMU by clearing sleep bit
void imuWake() {
  byte current = readI2CByte(PWR_MGMT0_REG);
  current &= ~SLEEP_BIT;
  writeI2CByte(PWR_MGMT0_REG, current);
  Serial.println(">>> IMU put to ACTIVE mode.");
}

// Sleep IMU by setting sleep bit
void imuSleep() {
  byte current = readI2CByte(PWR_MGMT0_REG);
  current |= SLEEP_BIT;
  writeI2CByte(PWR_MGMT0_REG, current);
  Serial.println(">>> IMU put to SLEEP mode.");
}

// Read accel and gyro data from IMU
bool readIMUData(LogEntry &entry) {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(ACCEL_DATA_START);
  if (Wire.endTransmission(false) != 0) return false;

  int bytesRead = Wire.requestFrom(IMU_ADDRESS, 12);
  if (bytesRead != 12) return false;

  entry.ax = (Wire.read() << 8) | Wire.read();
  entry.ay = (Wire.read() << 8) | Wire.read();
  entry.az = (Wire.read() << 8) | Wire.read();

  entry.gx = (Wire.read() << 8) | Wire.read();
  entry.gy = (Wire.read() << 8) | Wire.read();
  entry.gz = (Wire.read() << 8) | Wire.read();

  entry.timestamp = millis();
  return true;
}

// Write collected data to CSV file on SPIFFS
void exportCSV() {
  Serial.println("Starting CSV export to /imu_log.csv ...");
  File file = SPIFFS.open("/imu_log.csv", FILE_WRITE);
  if (!file) {
    Serial.println("Failed to open file for writing!");
    return;
  }

  // Write CSV header
  file.println("Cycle,Mode,Timestamp_ms,AccelX,AccelY,AccelZ,GyroX,GyroY,GyroZ");

  for (int i = 0; i < logIndex; i++) {
    LogEntry &e = logBuffer[i];
    String modeStr = e.activeMode ? "Active" : "Sleep";
    file.printf("%d,%s,%lu,%d,%d,%d,%d,%d,%d\n",
                e.cycle, modeStr.c_str(), e.timestamp,
                e.ax, e.ay, e.az, e.gx, e.gy, e.gz);
  }

  file.close();
  Serial.println("CSV export completed.");
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("Starting IMU sleep/active data collection...");

  if (!SPIFFS.begin(true)) {
    Serial.println("SPIFFS mount failed!");
    while (1) delay(1000);
  }

  Wire.begin(10, 1);
  byte whoAmI = readI2CByte(WHO_AM_I_REG);
  Serial.print("IMU WHO_AM_I register: 0x");
  Serial.println(whoAmI, HEX);

  if (whoAmI != 0x60 && whoAmI != 0x68) {
    Serial.println("IMU not detected. Check wiring!");
    while (1) delay(1000);
  }

  imuWake();
}

void loop() {
  for (int cycle = 1; cycle <= TOTAL_CYCLES; cycle++) {
    // Sleep mode period
    Serial.printf("Cycle %d: Entering SLEEP mode for 1 minute...\n", cycle);
    imuSleep();
    // Log a marker entry for sleep (no sensor data)
    if (logIndex < MAX_SAMPLES) {
      logBuffer[logIndex++] = {millis(), 0,0,0,0,0,0, cycle, false};
    }
    delay(SLEEP_DURATION_MS);

    // Active mode period
    Serial.printf("Cycle %d: Entering ACTIVE mode for 1 minute...\n", cycle);
    imuWake();

    unsigned long startTime = millis();
    while (millis() - startTime < ACTIVE_DURATION_MS) {
      if (logIndex >= MAX_SAMPLES) {
        Serial.println("Log buffer full, stopping data collection.");
        break;
      }

      LogEntry entry;
      if (readIMUData(entry)) {
        entry.cycle = cycle;
        entry.activeMode = true;
        logBuffer[logIndex++] = entry;
      } else {
        Serial.println("Failed to read IMU data.");
      }
      delay(LOG_INTERVAL_MS);
    }
  }

  Serial.println("All cycles complete. Exporting data...");
  exportCSV();

  Serial.println("Done. Halting.");
  while (true) delay(1000);
}
