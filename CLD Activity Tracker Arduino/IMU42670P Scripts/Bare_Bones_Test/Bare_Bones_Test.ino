#include <Wire.h>
#include "ICM42670P.h" // Your other include

// Instantiate the IMU object
ICM42670 IMU(Wire, 0);

void setup() {
  // Start Serial and wait a second for it to be ready
  Serial.begin(115200);
  delay(1000); 
  Serial.println("\n\n--- Bare-bones IMU Test ---");

  // Checkpoint 1: Before I2C
  Serial.println("Checkpoint 1: Starting Wire on pins 10 (SDA) and 8 (SCL)...");
  Wire.begin(10, 8);
  Serial.println("Checkpoint 2: Wire.begin() complete.");

  // Checkpoint 2: Before IMU.begin()
  Serial.println("Checkpoint 3: Calling IMU.begin()...");
  int ret = IMU.begin();
  Serial.println("Checkpoint 4: IMU.begin() finished.");

  // Checkpoint 3: Check result
  if (ret != 0) {
    Serial.print("IMU initialization FAILED with code: ");
    Serial.println(ret);
    while(1); // Stop here
  }
  
  Serial.println("IMU initialization SUCCEEDED.");

  // Checkpoint 4: Before starting Accel
  Serial.println("Checkpoint 5: Calling startAccel()...");
  ret = IMU.startAccel(50, 2); // 50Hz, +/- 2G
  Serial.println("Checkpoint 6: startAccel() finished.");

  if (ret != 0) {
    Serial.print("Failed to start accelerometer. Status: ");
    Serial.println(ret);
    while (1); // Stop here
  }
}

void loop() {
  Serial.println("Loop is running. Reading data...");

  inv_imu_sensor_event_t sensor_event;

  // We are still calling this function to get the data
  int status = IMU.getDataFromRegisters(sensor_event);

  if (status == 0) {
    
    // --- WE ARE REMOVING THE "if (IMU.isAccelDataValid...)" CHECK ---
    
    // Let's just print the data directly and see what's in there.
    // The data is in the 'accel' array: accel[0]=X, accel[1]=Y, accel[2]=Z
    // The values are in milli-g's, so we divide by 1000.0 to get G's.
    float ax = sensor_event.accel[0] / 1000.0f;
    float ay = sensor_event.accel[1] / 1000.0f;
    float az = sensor_event.accel[2] / 1000.0f;

    // Print the accelerometer data
    Serial.print("X: ");
    Serial.print(ax, 4); 
    Serial.print(" g\t");

    Serial.print("Y: ");
    Serial.print(ay, 4);
    Serial.print(" g\t");

    Serial.print("Z: ");
    Serial.println(az, 4);

  } else {
    // This part is still important
    Serial.print("getDataFromRegisters() failed with status: ");
    Serial.println(status);
  }

  delay(500); // Slowed down delay to make it easier to read
}
