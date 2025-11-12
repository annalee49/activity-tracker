// --- BLE Includes ---
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>

// --- IMU & File System Includes ---
#include <Wire.h>     // We only need the core Wire library
#include <math.h>
#include "FS.h"
#include "SPIFFS.h"

// --- BLE Definitions ---
#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
// Main characteristic for live data and commands
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8" 
// New characteristic just for file transfer
#define FILE_TRANSFER_CHAR_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a9"

BLECharacteristic *pCharacteristic;
BLECharacteristic *pFileCharacteristic; 

// --- IMU Definitions ---
// These are the I2C register addresses we need from the datasheet
#define IMU_ADDRESS   0x68   // I2C address (from our scanner)
#define WHO_AM_I_REG  0x75   // Who Am I register
#define PWR_MGMT0_REG 0x4E   // Power Management 0
#define ACCEL_DATA_X1 0x1F   // First byte of Accelerometer data
// We will read 12 bytes total (Accel X/Y/Z, Gyro X/Y/Z)

struct LogEntry {
  unsigned long timestamp; // 4 bytes
  int16_t ax, ay, az;      // 2 bytes each (6 total)
  int16_t gx, gy, gz;      // 2 bytes each (6 total)
};
const char* filename = "/imu_data.bin"; // File name for stored data

// --- Timer Control ---
unsigned long lastLogTime = 0;
const unsigned long logInterval = 25; // Log to file every 25ms (40Hz)
// --- Live BLE Send Timer Removed ---

// --- Control Flags ---
const int ledPin = 7;
bool isLogging = false;

// --- Function Prototypes (Forward Declarations) ---
void startLogging();
void stopLogging();
void exportFileData(); 
void exportFileOverBLE(); 

// --- OUR NEW CUSTOM LIBRARY FUNCTIONS ---

/**
 * @brief Reads a single byte from a specified I2C register.
 * @param reg The register address to read from.
 * @return The byte value read from the register.
 */
byte readI2CByte(byte reg) {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(reg);
  Wire.endTransmission(false); // `false` keeps the bus active (repeated start)
  
  Wire.requestFrom(IMU_ADDRESS, 1);
  return Wire.read();
}

/**
 * @brief Writes a single byte to a specified I2C register.
 * @param reg The register address to write to.
 * @param val The byte value to write.
 */
void writeI2CByte(byte reg, byte val) {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

/**
 * @brief Our new "begin" function. Wakes up the IMU.
 * @return 0 on success, -1 on failure.
 */
int my_imu_begin() {
  Wire.begin(10, 8); // Your SDA=10, SCL=8 pins
  Wire.setClock(50000L); // Use the slow clock fix
  
  byte whoAmI = readI2CByte(WHO_AM_I_REG);
  Serial.print("IMU Who Am I? Read: 0x");
  Serial.println(whoAmI, HEX);

  // We check for 0x68 (correct) or 0x60 (your corrupted value)
  // This makes our library robust to your specific hardware failure.
  if (whoAmI != 0x68 && whoAmI != 0x60) {
    Serial.println("IMU NOT found. Check wiring.");
    return -1;
  }
  
  Serial.println("IMU found. Waking up sensors...");
  // Write 0x0F to PWR_MGMT0 (0x4E) to enable Accel and Gyro
  writeI2CByte(PWR_MGMT0_REG, 0x0F);
  delay(10); // Give the sensors a moment to stabilize
  
  return 0; // Success!
}

/**
 * @brief Our new "read data" function.
 * @param a pointer to an int16_t array (size 6) to store the data.
 * @return 0 on success.
 */
int my_imu_read(int16_t* data) {
  // Start a transmission and point to the first data register
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(ACCEL_DATA_X1);
  Wire.endTransmission(false); // `false` keeps bus active
  
  // Request all 12 bytes of data (Accel + Gyro)
  int bytesRead = Wire.requestFrom(IMU_ADDRESS, 12);
  
  if (bytesRead != 12) {
    Serial.println("Failed to read 12 bytes from IMU!");
    return -5; // We'll use the same error code
  }

  // Read the 12 bytes in order (High byte first, then Low byte)
  data[0] = (Wire.read() << 8) | Wire.read(); // Accel X
  data[1] = (Wire.read() << 8) | Wire.read(); // Accel Y
  data[2] = (Wire.read() << 8) | Wire.read(); // Accel Z
  data[3] = (Wire.read() << 8) | Wire.read(); // Gyro X
  data[4] = (Wire.read() << 8) | Wire.read(); // Gyro Y
  data[5] = (Wire.read() << 8) | Wire.read(); // Gyro Z
  
  return 0; // Success
}
// --- END OF OUR CUSTOM LIBRARY ---


// --- BLE Callback Class ---
class MyCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      String value = pCharacteristic->getValue();
      if (value.length() > 0) {
        Serial.print("BLE received: ");
        Serial.println(value);
        if (value == "start") {
          startLogging();
        } else if (value == "stop") {
          stopLogging();
        } else if (value == "export_ble") { 
          exportFileOverBLE();
        }
      }
    }
};

void setup() {
  Serial.begin(115200);
  delay(2000);
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW);

  Serial.println("\n--- IMU Data Logger + Custom BLE ---");
  Serial.println("Type 'start', 'stop', 'export', 'export_ble', 'clear', 'status'"); 
  Serial.println("------------------------------------");

  Serial.println("Initializing SPIFFS...");
  if (!SPIFFS.begin(true)) {
    Serial.println("!! SPIFFS Mount Failed !!");
    while (1); 
  }
  Serial.println("SPIFFS Initialized.");

  Serial.println("Initializing ICM42670 IMU with custom library...");
  
  // --- CALL OUR NEW BEGIN FUNCTION ---
  int status = my_imu_begin(); 
  if (status != 0) {
    Serial.print("IMU init failed: "); Serial.println(status);
    while (1); // Stop here
  }
  Serial.println("IMU Initialized.");

  // --- Start BLE Server ---
  Serial.println("Starting BLE server...");
  BLEDevice::init("My_ESP32_IMU");
  BLEServer *pServer = BLEDevice::createServer();
  BLEService *pService = pServer->createService(SERVICE_UUID);

  // Create the main characteristic (for live data and commands)
  pCharacteristic = pService->createCharacteristic(
                                         CHARACTERISTIC_UUID,
                                         BLECharacteristic::PROPERTY_READ |
                                         BLECharacteristic::PROPERTY_WRITE |
                                         BLECharacteristic::PROPERTY_NOTIFY
                                       );
  pCharacteristic->addDescriptor(new BLE2902());
  pCharacteristic->setCallbacks(new MyCallbacks()); 
  pCharacteristic->setValue("IMU Ready");
  
  // --- Create the new file characteristic (for file transfer) ---
  pFileCharacteristic = pService->createCharacteristic(
                                         FILE_TRANSFER_CHAR_UUID,
                                         BLECharacteristic::PROPERTY_NOTIFY
                                       );
  pFileCharacteristic->addDescriptor(new BLE2902());
  // -------------------------------------------------------------
  
  pService->start();
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  BLEDevice::startAdvertising();
  Serial.println("BLE Server started. Advertising...");
  
  // Check if we should resume logging after a reboot
  if (SPIFFS.exists("/logging.flag")) {
    isLogging = true;
    digitalWrite(ledPin, HIGH);
    Serial.println("Rebooted. Logging is ON.");
  } else {
    isLogging = false;
    digitalWrite(ledPin, LOW);
    Serial.println("Rebooted. Logging is OFF.");
  }
}

void loop() {
  checkSerialCommands();

  // Timer 1: Log data to file at a fast rate (40Hz)
  if (isLogging && (millis() - lastLogTime >= logInterval)) {
    lastLogTime = millis();
    logIMUDataToFile(); // Log to SPIFFS
  }

  // --- LIVE BLE STREAMING REMOVED ---
  // Data is now only sent when you use the 'export_ble' command.
}

// --- Serial Command Functions ---
// (These are unchanged from your code)
void checkSerialCommands() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "start") {
      startLogging();
    }  
    else if (cmd == "stop") {
      stopLogging();
    }
    else if (cmd == "export") {
      stopLogging(); // Stop logging to make sure file is saved
      exportFileData();
    }
    // --- NEW COMMAND ---
    else if (cmd == "export_ble") {
      exportFileOverBLE();
    }
    else if (cmd == "clear") {
      Serial.println("\n!!! FORMATTING FILESYSTEM - ERASING ALL DATA !!!");
      SPIFFS.format();
      Serial.println("Please RESTART the board.");
      while (1);
    }
    else if (cmd == "status") {
      Serial.println("\n--- Filesystem Status ---");
      Serial.printf("Total: %lu bytes\n", SPIFFS.totalBytes());
      Serial.printf("Used:  %lu bytes\n", SPIFFS.usedBytes());
      Serial.printf("Usage: %.1f%%\n", (SPIFFS.usedBytes() * 100.0) / SPIFFS.totalBytes());
    }
  }
}

void startLogging() {
  if (!isLogging) {
    Serial.println("\n>>> Logging START <<<\n");
    File flagFile = SPIFFS.open("/logging.flag", FILE_WRITE);
    flagFile.close();
    digitalWrite(ledPin, HIGH);
    isLogging = true;
  } else {
    Serial.println("Already logging.");
  }
}

void stopLogging() {
  if (isLogging) {
    Serial.println("\n>>> Logging STOP <<<\n");
    SPIFFS.remove("/logging.flag");
    digitalWrite(ledPin, LOW);
    isLogging = false;
  } else {
    Serial.println("Already stopped.");
  }
}

// --- NEW FUNCTION TO DUMP FILE TO SERIAL ---
void exportFileData() {
  File file = SPIFFS.open(filename, FILE_READ);
  if (!file) {
    Serial.println("Failed to open file for reading");
    return;
  }

  Serial.println("\n--- START OF FILE DATA ---");
  // We send the raw binary data. This will look
  // like garbled text in the Serial Monitor. This is normal.
  
  byte buffer[64];
  while(file.available()) {
    int bytesRead = file.read(buffer, sizeof(buffer));
    Serial.write(buffer, bytesRead); // Use Serial.write for raw data
  }
  
  file.close();
  Serial.println("\n--- END OF FILE DATA ---");
}

// --- NEW FUNCTION TO DUMP FILE OVER BLE ---
void exportFileOverBLE() {
  stopLogging(); // Stop logging to make sure file is saved
  
  File file = SPIFFS.open(filename, FILE_READ);
  if (!file) {
    Serial.println("Failed to open file for BLE export");
    return;
  }
  
  Serial.println("Starting BLE file export...");

  byte buffer[50]; // Small chunks for BLE
  while(file.available()) {
    int bytesRead = file.read(buffer, sizeof(buffer));
    if (bytesRead > 0) {
      pFileCharacteristic->setValue(buffer, bytesRead);
      pFileCharacteristic->notify();
      delay(20); // IMPORTANT: Give the BLE stack time to send
    }
  }
  
  file.close();

  // Send a final message to signal the end of the transfer
  delay(100); // Wait a bit
  pFileCharacteristic->setValue("END_OF_FILE");
  pFileCharacteristic->notify();

  Serial.println("BLE file export complete.");
}


// --- Data Functions (Now using our new library) ---

// An array to hold the 6 sensor values
int16_t sensor_data[6]; // 0=ax, 1=ay, 2=az, 3=gx, 4=gy, 5=gz

// --- sendIMUDataOverBLE() function has been removed (no live streaming) ---


void logIMUDataToFile() {
  // --- MODIFIED LOGIC ---
  // Check if file system is getting full. Let's use 98%
  if (SPIFFS.usedBytes() > (SPIFFS.totalBytes() * 0.98)) {
    Serial.println("!!! MEMORY FULL - LOGGING STOPPED !!!");
    stopLogging(); // Automatically stop logging
    return;        // Do not write any more data
  }
  // --------------------

  // --- CALL OUR NEW READ FUNCTION ---
  int status = my_imu_read(sensor_data);
  if (status != 0) {
    Serial.print("IMU read error (File): "); Serial.println(status);
    return;
  }

  // Populate the binary log structure
  LogEntry currentLog;
  currentLog.timestamp = millis();
  currentLog.ax = sensor_data[0];
  currentLog.ay = sensor_data[1];
  currentLog.az = sensor_data[2];
  currentLog.gx = sensor_data[3];
  currentLog.gy = sensor_data[4];
  currentLog.gz = sensor_data[5];

  File file = SPIFFS.open(filename, FILE_APPEND);
  if (file) {
    file.write((uint8_t*)&currentLog, sizeof(LogEntry));
    file.close();
  }

  Serial.printf("Logged to file: t=%lu ms\n", currentLog.timestamp);
}