#include "ICM42670P.h"

// Instantiate an ICM42670 object, telling it to use the Wire library for I2C
ICM42670 IMU(Wire, 0);

void setup() {
  Serial.begin(115200);
  while (!Serial);
  Serial.println("ICM42670 Accelerometer Reading");

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
  // We'll set it to a 50Hz Output Data Rate (ODR) and a +/- 2G Full-Scale Range (FSR).
  status = IMU.startAccel(50, 2);
  if (status != 0) {
    Serial.print("Failed to start accelerometer. Status: ");
    Serial.println(status);
    while (1); // Stop
  }
}

void loop() {
  // Add this line for debugging
  Serial.println("Loop start...");
  
  // Create a sensor event object to store the data from the IMU
  inv_imu_sensor_event_t sensor_event;

  // Use the correct function to read the data from the sensor's registers
  int status = IMU.getDataFromRegisters(sensor_event);

  // Add this block to check the status
  if (status != 0) {
    Serial.print("IMU.getDataFromRegisters() failed with status: ");
    Serial.println(status);
    delay(500);
    return; // Skip the rest of the loop
  }

  if (status == 0) {
    // Check if the event contains valid accelerometer data
    if (IMU.isAccelDataValid(&sensor_event)) {
      
      // The data is in the 'accel' array: accel[0]=X, accel[1]=Y, accel[2]=Z
      // The values are in milli-g's, so we divide by 1000.0 to get G's.
      float ax = sensor_event.accel[0] / 1000.0f;
      float ay = sensor_event.accel[1] / 1000.0f;
      float az = sensor_event.accel[2] / 1000.0f;

      // Print the accelerometer data
      Serial.print("X: ");
      Serial.print(ax, 4); // Print with 4 decimal places
      Serial.print(" g\t"); // '\t' is a tab

      Serial.print("Y: ");
      Serial.print(ay, 4);
      Serial.print(" g\t");

      Serial.print("Z: ");
      Serial.println(az, 4);
    }
    else {
    // Add this else block for debugging
    Serial.println("Data read, but it's not valid accel data.");
  }
  }

  delay(100); // Wait 100 milliseconds
}
