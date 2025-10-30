#include <Wire.h>

void setup() {
  // Use the same I2C pins as your project
  Wire.begin(10, 8); // (SDA=10, SCL=8)
  
  Serial.begin(115200);
  while (!Serial); // Wait for Serial to be ready
  Serial.println("\nI2C Scanner");
  Serial.println("Scanning for devices on SDA=10, SCL=8...");
}

void loop() {
  byte error, address;
  int nDevices;

  nDevices = 0;
  for (address = 1; address < 127; address++) {
    // The i2c_scanner uses the return value of
    // Wire.endTransmission to see if a device is attached.
    Wire.beginTransmission(address);
    error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("I2C device found at address 0x");
      if (address < 16)
        Serial.print("0");
      Serial.print(address, HEX);
      Serial.println("  !");
      nDevices++;
    } else if (error == 4) {
      Serial.print("Unknown error at address 0x");
      if (address < 16)
        Serial.print("0");
      Serial.println(address, HEX);
    }
  }
  if (nDevices == 0)
    Serial.println("No I2C devices found");
  else
    Serial.println("Scan complete.");

  delay(5000); // Wait 5 seconds and scan again
}
