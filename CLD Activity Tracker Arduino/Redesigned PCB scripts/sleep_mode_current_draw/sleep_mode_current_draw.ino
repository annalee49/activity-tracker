#include <Wire.h>

#define IMU_ADDRESS 0x68
#define WHO_AM_I_REG 0x75
#define PWR_MGMT0_REG 0x1F
#define SLEEP_BIT 0x80 // Bit 7 in PWR_MGMT0 register

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

void imuSleep() {
  byte current = readI2CByte(PWR_MGMT0_REG);
  current |= SLEEP_BIT;
  writeI2CByte(PWR_MGMT0_REG, current);
  Serial.println(">>> IMU put to SLEEP mode.");
}

void imuWake() {
  byte current = readI2CByte(PWR_MGMT0_REG);
  current &= ~SLEEP_BIT; // Clear sleep bit to wake IMU
  writeI2CByte(PWR_MGMT0_REG, current);
  Serial.println(">>> IMU put to ACTIVE mode.");
}

void setup() {
  Serial.begin(115200);
  delay(2000); // Wait for serial connection

  Wire.begin(10, 1); // SDA=GPIO10, SCL=GPIO1
  Serial.println("I2C initialized on SDA=GPIO10, SCL=GPIO1");

  byte whoAmI = readI2CByte(WHO_AM_I_REG);
  Serial.print("IMU WHO_AM_I register: 0x");
  Serial.println(whoAmI, HEX);

  if (whoAmI != 0x60) {
    Serial.println("IMU not detected. Check wiring!");
    while (1) delay(1000);
  }
  Serial.println("IMU detected successfully.");

  // Start with IMU awake
  imuWake();
}

void loop() {
  const int cycles = 5;
  const unsigned long sleepDuration = 60UL * 1000UL; // 1 minute in ms
  const unsigned long activeDuration = 60UL * 1000UL; // 1 minute in ms

  for (int i = 0; i < cycles; i++) {
    Serial.printf("Cycle %d: Going to SLEEP mode for 1 minute...\n", i + 1);
    imuSleep();
    delay(sleepDuration);

    Serial.printf("Cycle %d: Going to ACTIVE mode for 1 minute...\n", i + 1);
    imuWake();
    delay(activeDuration);
  }

  Serial.println("Completed 5 sleep/active cycles. Halting.");
  while (true) delay(1000); // Stop here
}
