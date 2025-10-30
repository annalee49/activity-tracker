#include <Wire.h>
#include <math.h>       // <-- ADD THIS LINE for math functions (atan2, sqrt)
#include "ICM42670P.h"

// Instantiate an ICM42670 object, telling it to use the Wire library for I2C
ICM42670 IMU(Wire, 0);

// --- Your setup() function stays exactly the same ---
void setup() {
  Serial.begin(115200);
  while (!Serial);
  Serial.println("ICM42670 Accelerometer and Tilt Reading");

  // Manually start the I2C bus on your specific pins (SDA=10, SCL=8)
  Wire.begin(10, 8);

  // Initialize the IMU
  int status = IMU.begin();
  if (status != 0) {
    Serial.print("IMU initialization failed. Status: ");
    Serial.println(status);
    while (1); // Stop
  }
  Serial.println("IMU initialized successfully.");

  // Use the correct function to start the accelerometer.
  status = IMU.startAccel(50, 2); // 50Hz, +/- 2G
  if (status != 0) {
    Serial.print("Failed to start accelerometer. Status: ");
    Serial.println(status);
    while (1); // Stop
  }
}

// --- Changes are in the loop() function ---
void loop() {
  inv_imu_sensor_event_t sensor_event;

  // Use the correct function to read the data from the sensor's registers
  int status = IMU.getDataFromRegisters(sensor_event);

  if (status == 0) {
    // We are still bypassing the "isAccelDataValid" check
    
    // Get the acceleration data in G's
    float ax = sensor_event.accel[0] / 1000.0f;
    float ay = sensor_event.accel[1] / 1000.0f;
    float az = sensor_event.accel[2] / 1000.0f;

    // --- NEW TILT CALCULATION ---
    // Calculate Roll and Pitch in degrees
    float roll = atan2(ay, az) * 180.0 / M_PI;
    float pitch = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / M_PI;

    // --- UPDATED PRINT STATEMENTS ---
    // Print the acceleration (position) data
    Serial.print("Accel X: ");
    Serial.print(ax, 2); // 2 decimal places is fine
    Serial.print(" g\tY: ");
    Serial.print(ay, 2);
    Serial.print(" g\tZ: ");
    Serial.print(az, 2);
    Serial.print(" g");

    // Print the tilt data
    Serial.print("\t  ||  Roll: ");
    Serial.print(roll, 1); // 1 decimal place is fine
    Serial.print(" °\tPitch: ");
    Serial.print(pitch, 1);
    Serial.println(" °");
    
  } else {
    // This part is still important
    Serial.print("getDataFromRegisters() failed with status: ");
    Serial.println(status);
  }

  delay(250); // A slightly faster delay
}
