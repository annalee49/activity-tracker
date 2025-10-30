#include <Wire.h>
#include <math.h>
#include "ICM42670P.h"
#include "FS.h"
#include "SPIFFS.h"

void logIMUData();
void exportCSV();

// Instantiate IMU
ICM42670 IMU(Wire, 0);

// File name for stored data
const char* filename = "/imu_data.csv";

// Button Setup
const int buttonPin = 9; // GPIO 9 for your IO9_Boot button
bool lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50; // 50ms debounce

// Timer control
unsigned long lastLogTime = 0;
const unsigned long logInterval = 250; // ms

// --- NEW ---
// This flag will control logging.
bool isLogging = false;

void setup() {
  Serial.begin(115200);
  // Give you 2 seconds to open the Serial Monitor
  delay(2000); 
  Serial.println("\n--- IMU Data Logger ---");
  Serial.println("Type 'start' to begin logging.");
  Serial.println("Type 'stop' to pause logging.");
  Serial.println("Type 'export' to print all saved CSV data.");
  Serial.println("Type 'clear' to erase all data.");
  Serial.println("Type 'status' to view memory status.");
  Serial.println("-------------------------");

  Serial.println("Initializing SPIFFS...");
  // Try to mount the file system
  if (!SPIFFS.begin(true)) {
    Serial.println("!! SPIFFS Mount Failed !!");
    Serial.println("!! Type 'clear' to format the filesystem !!");
    while (1) {
      // We are stuck, but we can still check for the 'clear' command
      checkSerialCommands();
      delay(100);
    }
  }
  Serial.println("SPIFFS Initialized.");
  pinMode(buttonPin, INPUT_PULLUP);
  Serial.println("Initializing ICM42670 IMU...");
  Wire.begin(10, 8);
  int status = IMU.begin();
  if (status != 0) {
    Serial.print("IMU init failed: "); Serial.println(status);
    while (1); // Stop
  }
  Serial.println("IMU Initialized.");

  // Start accelerometer and gyro
  IMU.startAccel(50, 2);
  IMU.startGyro(50, 250);
  
  isLogging = false; // Don't start logging until user types 'start'
  Serial.println("\nReady. Type 'start' to begin.");
}

void loop() {
  // This new function checks for user input
  checkSerialCommands();
  
  // --- ADD THIS LINE ---
  checkButton(); // Run the button-checking code every loop

  // Only log data if the 'isLogging' flag is true
  if (isLogging && (millis() - lastLogTime >= logInterval)) {
    lastLogTime = millis();
    logIMUData();
  }
}

// --- NEW FUNCTION ---
// Checks for a physical button press
void checkButton() {
  bool currentButtonState = digitalRead(buttonPin);

  // Check if the button state has changed (pressed or released)
  if (currentButtonState != lastButtonState) {
    lastDebounceTime = millis(); // Reset the debounce timer
  }

  // Check if the button has been in its new state for long enough
  if ((millis() - lastDebounceTime) > debounceDelay) {
    
    // Check if the button was just pressed (i.e., it went from HIGH to LOW)
    if (currentButtonState == LOW && lastButtonState == HIGH) {
      
      // --- Toggle the logging state ---
      isLogging = !isLogging; 

      if (isLogging) {
        Serial.println("\n>>> Logging START (via button) <<<\n"); // [cite: 17]
      } else {
        Serial.println("\n>>> Logging STOP (via button) <<<\n"); // [cite: 19]
      }
    }
  }
  
  // Save the current button state for next loop
  lastButtonState = currentButtonState;
}

// --- NEW FUNCTION ---
// Checks for commands from the Serial Monitor
void checkSerialCommands() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim(); // Remove any whitespace

    if (cmd == "start") {
      // 'start' logic...
      if (!isLogging) {
        Serial.println("\n>>> Logging START <<<\n");
        isLogging = true;
      } else {
        Serial.println("Already logging.");
      }
    } 
    else if (cmd == "stop") {
      // 'stop' logic...
      if (isLogging) {
        Serial.println("\n>>> Logging STOP <<<\n");
        isLogging = false;
      } else {
        Serial.println("Already stopped.");
      }
    }
    else if (cmd == "export") {
      // 'export' logic...
      isLogging = false; // Stop logging
      Serial.println("\n>>> Exporting CSV... <<<");
      exportCSV();
    }
    else if (cmd == "clear") {
      // 'clear' logic...
      isLogging = false; // Stop logging
      Serial.println("\n!!! FORMATTING FILESYSTEM - ERASING ALL DATA !!!");
      if (SPIFFS.format()) {
        Serial.println("Filesystem formatted successfully.");
        Serial.println("Please RESTART the board now by pressing the RST button.");
      } else {
        Serial.println("Filesystem format FAILED.");
      }
      // After formatting, we must restart
      while(1); // This correctly freezes the board ONLY for the 'clear' command
    }
    // --- THIS IS THE CORRECT PLACEMENT ---
    else if (cmd == "status") {
      Serial.println("\n--- Filesystem Status ---");
      Serial.printf("Total Space: %lu bytes\n", SPIFFS.totalBytes());
      Serial.printf("Used Space:  %lu bytes\n", SPIFFS.usedBytes());
      Serial.printf("Usage:       %.1f%%\n", (SPIFFS.usedBytes() * 100.0) / SPIFFS.totalBytes());
      Serial.println("-------------------------");
    }
  }
}

void logIMUData() {
  // --- NEW MEMORY CHECK ---
  if (SPIFFS.usedBytes() > (SPIFFS.totalBytes() * 0.95)) {
    Serial.println("WARNING: Memory almost full! Deleting old log to make space...");
    SPIFFS.remove(filename); 
    Serial.println("Old log file removed. Starting new log.");
  }
  // --- END NEW MEMORY CHECK ---

  inv_imu_sensor_event_t sensor_event;
  int status = IMU.getDataFromRegisters(sensor_event);
  if (status != 0) {
    Serial.print("IMU read error: "); Serial.println(status);
    return;
  }

  // --- Use the correct math ---
  float ax = sensor_event.accel[0] / 16384.0f;
  float ay = sensor_event.accel[1] / 16384.0f;
  float az = sensor_event.accel[2] / 16384.0f;
  float gx = sensor_event.gyro[0] / 131.0f;
  float gy = sensor_event.gyro[1] / 131.0f;
  float gz = sensor_event.gyro[2] / 131.0f;
  unsigned long t = millis();

  File file = SPIFFS.open(filename, FILE_APPEND);
  if (file) {
    // --- THIS BLOCK IS NOW REMOVED ---
    // if (file.size() == 0) { ... } 
    
    // Write data
    file.printf("%lu,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f\n",
                t, ax, ay, az, gx, gy, gz);
    file.close();
  }
  
  Serial.printf("Logged: t=%lu ms\n", t);
}

void exportCSV() {
  File file = SPIFFS.open(filename, FILE_READ);
  if (!file || file.size() == 0) {
    Serial.println("File not found or is empty. Nothing to export.");
    return;
  }

  Serial.println("--- CSV EXPORT START ---");
  
  // --- ADD THIS LINE TO PRINT THE HEADER ---
  Serial.println("timestamp(ms),ax(g),ay(g),az(g),gx(dps),gy(dps),gz(dps)");
  
  // Now, print the file's raw data
  while (file.available()) {
    Serial.write(file.read());
  }
  Serial.println("\n--- CSV EXPORT END ---");
  file.close();
}
