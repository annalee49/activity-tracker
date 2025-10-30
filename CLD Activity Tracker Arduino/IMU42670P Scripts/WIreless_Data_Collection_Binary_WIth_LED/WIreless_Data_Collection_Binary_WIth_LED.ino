#include <Wire.h>
#include <math.h>
#include "ICM42670P.h"
#include "FS.h"
#include "SPIFFS.h"

struct LogEntry {
  unsigned long timestamp; // 4 bytes
  int16_t ax, ay, az;      // 2 bytes each (6 total)
  int16_t gx, gy, gz;      // 2 bytes each (6 total)
};

// Instantiate IMU
ICM42670 IMU(Wire, 0);

// File name for stored data
const char* filename = "/imu_data.csv";

// Timer control
unsigned long lastLogTime = 0;
const unsigned long logInterval = 250; // ms


// --- NEW ---
// Define the pin for the User LED
const int ledPin = 7; // Use the "Regular" LED on GPIO 7
// --- END NEW ---

// --- NEW ---
// This flag will control logging.
bool isLogging = false;

void setup() {
  Serial.begin(115200);
  delay(2000); // Give you 2 seconds to open the Serial Monitor
  // --- NEW ---
  pinMode(ledPin, OUTPUT);      // Set the LED pin as an output
  digitalWrite(ledPin, LOW);    // Start with the LED off
  // --- END NEW ---
  Serial.println("\n--- IMU Data Logger ---");
  Serial.println("Type 'start', 'stop', 'export', 'clear', 'status'");
  Serial.println("-------------------------");

  Serial.println("Initializing SPIFFS...");
  if (!SPIFFS.begin(true)) {
    Serial.println("!! SPIFFS Mount Failed !!");
    Serial.println("!! Type 'clear' to format the filesystem !!");
    while (1) {
      checkSerialCommands();
      delay(100);
    }
  }
  Serial.println("SPIFFS Initialized.");

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
  
  // --- NEW LOGIC HERE ---
  // Check if we were logging before the reboot
  if (SPIFFS.exists("/logging.flag")) {
    isLogging = true;
    digitalWrite(ledPin, HIGH); // --- NEW: Turn LED ON
    Serial.println("Rebooted. Logging is ON.");
    Serial.println("Type 'stop' to pause.");
  } else {
    isLogging = false;
    digitalWrite(ledPin, LOW);  // --- NEW: Make sure LED is OFF
    Serial.println("Rebooted. Logging is OFF.");
    Serial.println("Type 'start' to begin.");
  }
}

void loop() {
  // This new function checks for user input
  checkSerialCommands();

  // Only log data if the 'isLogging' flag is true
  if (isLogging && (millis() - lastLogTime >= logInterval)) {
    lastLogTime = millis();
    logIMUData();
  }
}

void exportCSV() {
  File file = SPIFFS.open(filename, FILE_READ);
  if (!file || file.size() == 0) {
    Serial.println("File not found or is empty. Nothing to export.");
    return;
  }

  Serial.println("--- CSV EXPORT START ---");
  // The header now includes roll and pitch, which we will calculate live
  Serial.println("timestamp(ms),ax(g),ay(g),az(g),gx(dps),gy(dps),gz(dps),roll(deg),pitch(deg)");
  
  LogEntry entry; // A 16-byte struct to hold data from the file

  // Read the file, one 'LogEntry' at a time
  while (file.read((uint8_t*)&entry, sizeof(LogEntry)) == sizeof(LogEntry)) {
    
    // --- Do the conversion math HERE ---
    float ax_g = entry.ax / 16384.0f;
    float ay_g = entry.ay / 16384.0f;
    float az_g = entry.az / 16384.0f;
    float gx_dps = entry.gx / 131.0f;
    float gy_dps = entry.gy / 131.0f;
    float gz_dps = entry.gz / 131.0f;
    
    // Calculate roll/pitch live
    float roll = atan2(ay_g, az_g) * 180.0 / M_PI;
    float pitch = atan2(-ax_g, sqrt(ay_g * ay_g + az_g * az_g)) * 180.0 / M_PI;

    // Now, print the full CSV line
    Serial.printf("%lu,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.2f,%.2f\n",
                  entry.timestamp, ax_g, ay_g, az_g,
                  gx_dps, gy_dps, gz_dps, roll, pitch);
  }
  
  Serial.println("\n--- CSV EXPORT END ---");
  file.close();
}

// --- NEW FUNCTION ---
// Checks for commands from the Serial Monitor
void checkSerialCommands() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim(); // Remove any whitespace

    if (cmd == "start") {
      if (!isLogging) {
        Serial.println("\n>>> Logging START <<<\n");
        // Create the flag file
        File flagFile = SPIFFS.open("/logging.flag", FILE_WRITE);
        flagFile.close();
        digitalWrite(ledPin, HIGH); // --- NEW: Turn LED ON
        isLogging = true;
      } else {
        Serial.println("Already logging.");
      }
    } 
    else if (cmd == "stop") {
      if (isLogging) {
        Serial.println("\n>>> Logging STOP <<<\n");
        // Delete the flag file
        SPIFFS.remove("/logging.flag");
        digitalWrite(ledPin, LOW); // --- NEW: Turn LED OFF
        isLogging = false;
      } else {
        Serial.println("Already stopped.");
      }
    }
    else if (cmd == "export") {
      // 'export' logic...
      isLogging = false; // Stop logging
      digitalWrite(ledPin, LOW); // --- NEW: Turn LED OFF
      Serial.println("\n>>> Exporting CSV... <<<");
      exportCSV();
    }
    else if (cmd == "clear") {
      // 'clear' logic...
      isLogging = false; // Stop logging
      digitalWrite(ledPin, LOW); // --- NEW: Turn LED OFF
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

  // --- NEW: Use a struct to hold the RAW data ---
  LogEntry currentLog;

  currentLog.timestamp = millis();
  
  // Store the raw int16_t data directly. NO division!
  currentLog.ax = sensor_event.accel[0];
  currentLog.ay = sensor_event.accel[1];
  currentLog.az = sensor_event.accel[2];
  currentLog.gx = sensor_event.gyro[0];
  currentLog.gy = sensor_event.gyro[1];
  currentLog.gz = sensor_event.gyro[2];
  
  File file = SPIFFS.open(filename, FILE_APPEND);
  if (file) {
    // Write the raw 16 bytes of the struct
    file.write((uint8_t*)&currentLog, sizeof(LogEntry));
    file.close();
  }
  
  Serial.printf("Logged: t=%lu ms\n", currentLog.timestamp);
}
