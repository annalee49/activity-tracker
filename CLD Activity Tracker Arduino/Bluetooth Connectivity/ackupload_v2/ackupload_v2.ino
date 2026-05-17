// --- BLE Includes ---
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>

// --- IMU & File System Includes ---
#include <Wire.h> 
#include <math.h>
#include <ICM42670P.h>
#include "FS.h"
#include "SPIFFS.h"

ICM42670 IMU(Wire, 0);
volatile bool startTransfer = false;

// --- BLE Definitions ---
#define SERVICE_UUID             "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID     "beb5483e-36e1-4688-b7f5-ea07361b26a8" 
#define FILE_TRANSFER_CHAR_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a9"

BLECharacteristic *pCharacteristic;
BLECharacteristic *pFileCharacteristic; 

// --- IMU Definitions ---
struct LogEntry {
  unsigned long timestamp; // 4 bytes
  int16_t ax, ay, az;      // 2 bytes each (6 total)
  int16_t gx, gy, gz;      // 2 bytes each (6 total)
}; // Total: 16 bytes
const char* filename = "/imu_data.bin"; 

// --- Timer Control ---
unsigned long lastLogTime = 0;
const unsigned long logInterval = 25; // Log to file every 25ms (40Hz)

// --- Control Flags ---
const int ledPin = 7;
bool isLogging = false;
volatile bool clientReadyForNextPacket = false; // <-- NEW: Flag for ACK system

// --- Function Prototypes (Forward Declarations) ---
void startLogging();
void stopLogging();
void exportFileData(); 
void exportFileOverBLE(); 

// --- BLE Callback Class ---
class MyCallbacks: public BLECharacteristicCallbacks {
    // --- MODIFIED: Added "ACK" handler ---
    void onWrite(BLECharacteristic *pCharacteristic) {
      String value = pCharacteristic->getValue();
      if (value.length() > 0) {
//        Serial.print("BLE received: ");
        Serial.println(value);
        if (value == "start") {
          startLogging();
        } else if (value == "stop") {
          stopLogging();
        } else if (value == "export_ble") { 
          startTransfer = true;
        } 
        // --- NEW: Handle the ACK from the client ---
        else if (value == "ACK") {
          clientReadyForNextPacket = true; // Set the flag to unblock the sender
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

  Serial.println("Initializing ICM42670 IMU");
  
  Wire.begin(10, 8); 
  int status = IMU.begin(); 
  if (status != 0) { 
    Serial.print("IMU init failed: "); Serial.println(status);
    while (1);
  }
  IMU.startAccel(50, 2); 
  IMU.startGyro(50, 250); 
  Serial.println("IMU Initialized.");

  // --- Start BLE Server ---
  Serial.println("Starting BLE server...");
  BLEDevice::init("My_ESP32_IMU");

  // --- NEW: Request a larger MTU for faster transfers ---
  BLEDevice::setMTU(517); 
  
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
  pCharacteristic->setCallbacks(new MyCallbacks()); // <-- MODIFIED: This callback now handles ACKs
  pCharacteristic->setValue("IMU Ready");
  
  // --- Create the new file characteristic (for file transfer) ---
  pFileCharacteristic = pService->createCharacteristic(
                                        FILE_TRANSFER_CHAR_UUID,
                                        BLECharacteristic::PROPERTY_NOTIFY
                                      );
  pFileCharacteristic->addDescriptor(new BLE2902());
  
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

// Check if we need to start an export
  if (startTransfer) {
    startTransfer = false; // Reset flag
    exportFileOverBLE();   // Run the blocking function here, which is safe!
  }

  // Timer 1: Log data to file at a fast rate (40Hz)
  if (isLogging && (millis() - lastLogTime >= logInterval)) {
    lastLogTime = millis();
    logIMUDataToFile(); // Log to SPIFFS
  }
}

// --- Serial Command Functions ---
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
      stopLogging(); 
      exportFileData();
    }
    else if (cmd == "export_ble") {
      exportFileOverBLE();
    }
    else if (cmd == "clear") {
      Serial.println("\n--- Clearing Data File ---");
      if (SPIFFS.remove(filename)) {
        Serial.println("File /imu_data.bin deleted.");
      } else {
        Serial.println("Failed to delete file (or it didn't exist).");
      }
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
    if (SPIFFS.exists(filename)) {
      if (SPIFFS.remove(filename)) {
        Serial.println("Previous log file cleared.");
      } else {
        Serial.println("Could not clear previous log file.");
      }
    }

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

// --- DUMP FILE TO SERIAL (Unchanged) ---
void exportFileData() {
  File file = SPIFFS.open(filename, FILE_READ);
  if (!file) {
    Serial.println("Failed to open file for reading");
    return;
  }

  Serial.println("\n--- START OF FILE DATA ---");  
  byte buffer[64];
  while(file.available()) {
    int bytesRead = file.read(buffer, sizeof(buffer));
    Serial.write(buffer, bytesRead); 
  }
  
  file.close();
  Serial.println("\n--- END OF FILE DATA ---");
}


// --- COMPLETELY REWRITTEN FUNCTION ---
void exportFileOverBLE() {
  stopLogging(); // Stop logging to make sure file is saved
  
  File file = SPIFFS.open(filename, FILE_READ);
  if (!file) {
    Serial.println("Failed to open file for BLE export");
    return;
  }
  
  Serial.println("Starting BLE file export (ACK mode)...");

  // Based on 512-byte MTU, 16 bytes per entry. 30 entries = 480 bytes.
  const int entriesPerPacket = 30; 
  byte buffer[sizeof(LogEntry) * entriesPerPacket]; 
  
  // Allow the first packet to be sent immediately
  clientReadyForNextPacket = true;

  while(file.available()) {
    
    // --- This is our new waiting loop ---
    unsigned long waitStartTime = millis();
    while (!clientReadyForNextPacket) {
        // Wait here until the onWrite callback receives "ACK"

        // Safety timeout (3 seconds) in case client disconnects or fails
        if (millis() - waitStartTime > 3000) {
            Serial.println("!! Client ACK Timeout !! Aborting transfer.");
            file.close();
            return;
        }
        // This delay is CRITICAL. It yields processing time to the 
        // ESP32's BLE stack so it can actually receive the ACK.
        delay(5); 
    }
    // --- End of waiting loop ---

    // We have the ACK, so read the next chunk of data
    int bytesRead = file.read(buffer, sizeof(buffer));
    
    if (bytesRead > 0) {
      // Set the flag to false *before* sending.
      // We will now wait for the next ACK.
      clientReadyForNextPacket = false; 
      
      pFileCharacteristic->setValue(buffer, bytesRead);
      pFileCharacteristic->notify();
      
      // The old delay(50) is gone!
    }
  }
  
  file.close();

  // Send a final message to signal the end of the transfer
  delay(100); // Wait a bit for the last packet to clear
  pFileCharacteristic->setValue("END_OF_FILE");
  pFileCharacteristic->notify();

  Serial.println("BLE file export complete.");
}
// --- END OF REWRITTEN FUNCTION ---


// --- Data Functions (Unchanged) ---
int16_t sensor_data[6]; 

void logIMUDataToFile() {
  if (SPIFFS.usedBytes() > (SPIFFS.totalBytes() * 0.98)) {
    Serial.println("!!! MEMORY FULL - LOGGING STOPPED !!!");
    stopLogging(); 
    return;
  }

  inv_imu_sensor_event_t sensor_event; 
  int status = IMU.getDataFromRegisters(sensor_event); 
  if (status != 0) { 
    Serial.print("IMU read error (File): "); Serial.println(status);
    return;
  }

  // Populate the binary log structure
  LogEntry currentLog;
  currentLog.timestamp = millis();
  currentLog.ax = sensor_event.accel[0]; 
  currentLog.ay = sensor_event.accel[1];  
  currentLog.az = sensor_event.accel[2];  
  currentLog.gx = sensor_event.gyro[0];  
  currentLog.gy = sensor_event.gyro[1];  
  currentLog.gz = sensor_event.gyro[2];  

  File file = SPIFFS.open(filename, FILE_APPEND);  
  if (file) {
    file.write((uint8_t*)&currentLog, sizeof(LogEntry)); 
    file.close();
  }

  // Serial.printf("Logged: t=%lu, ax=%d, ay=%d, az=%d, gx=%d, gy=%d, gz=%d\n",
  //              currentLog.timestamp,
  //              currentLog.ax, currentLog.ay, currentLog.az,
  //              currentLog.gx, currentLog.gy, currentLog.gz);
}
