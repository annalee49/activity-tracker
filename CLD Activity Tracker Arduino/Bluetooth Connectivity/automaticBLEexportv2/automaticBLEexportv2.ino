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

// --- BLE Definitions ---
#define SERVICE_UUID            "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
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
volatile bool clientReadyForNextPacket = false; // Flag for ACK system

// --- Time Sync Variable ---
unsigned long timeOffset = 0; 

// --- Function Prototypes ---
void startLogging();
void stopLogging();
void exportFileData(); 
void exportFileOverBLE(); 
void logIMUDataToFile();

// --- BLE Callback Class ---
class MyCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      String value = pCharacteristic->getValue();
      if (value.length() > 0) {
        
        // 1. Handle ACK (Priority High - Keep it fast)
        if (value == "ACK") {
          clientReadyForNextPacket = true;
          return; 
        }

        Serial.print("BLE received: ");
        Serial.println(value);
        
        // 2. Handle Commands
        if (value == "start") {
          startLogging();
        } else if (value == "stop") {
          stopLogging();
        } else if (value == "export") { 
           // Stop logging first to ensure file is saved
           stopLogging();
           exportFileData(); 
        } else if (value == "export_ble") { 
          exportFileOverBLE();
        } 
        // 3. Handle Time Sync
        else if (value.startsWith("TIME:")) {
          String timeStr = value.substring(5); // Remove "TIME:"
          unsigned long phoneTime = strtoul(timeStr.c_str(), NULL, 10);
          timeOffset = phoneTime - millis(); 
          Serial.print("Time Synced. Offset: "); Serial.println(timeOffset);
        }
      }
    }
};

void setup() {
  Serial.begin(115200);
  delay(2000);
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW);

  Serial.println("\n--- IMU Data Logger + Auto-Export ---");

  // Init SPIFFS
  if (!SPIFFS.begin(true)) {
    Serial.println("!! SPIFFS Mount Failed !!");
    while (1); 
  }
  Serial.println("SPIFFS Initialized.");

  // Init IMU
  Wire.begin(10, 8); 
  if (IMU.begin() != 0) { 
    Serial.println("IMU init failed!");
    while (1);
  }
  IMU.startAccel(50, 2); 
  IMU.startGyro(50, 250); 
  Serial.println("IMU Initialized.");

  // Init BLE
  Serial.println("Starting BLE server...");
  BLEDevice::init("My_ESP32_IMU");
  BLEDevice::setMTU(517); // Maximize packet size
  
  BLEServer *pServer = BLEDevice::createServer();
  BLEService *pService = pServer->createService(SERVICE_UUID);

  // Main Command Characteristic
  pCharacteristic = pService->createCharacteristic(
                                        CHARACTERISTIC_UUID,
                                        BLECharacteristic::PROPERTY_READ |
                                        BLECharacteristic::PROPERTY_WRITE |
                                        BLECharacteristic::PROPERTY_NOTIFY
                                      );
  pCharacteristic->addDescriptor(new BLE2902());
  pCharacteristic->setCallbacks(new MyCallbacks()); 
  pCharacteristic->setValue("IMU Ready");
  
  // File Transfer Characteristic
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
  
  if (SPIFFS.exists("/logging.flag")) {
    isLogging = true;
    digitalWrite(ledPin, HIGH);
    Serial.println("Rebooted. Logging is ON.");
  }
}

void loop() {
  checkSerialCommands();

  if (isLogging && (millis() - lastLogTime >= logInterval)) {
    lastLogTime = millis();
    logIMUDataToFile(); 
  }
}

// --- Serial Command Functions ---
void checkSerialCommands() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "start") startLogging();
    else if (cmd == "stop") stopLogging();
    else if (cmd == "export") { stopLogging(); exportFileData(); }
    else if (cmd == "export_ble") exportFileOverBLE();
    else if (cmd == "clear") SPIFFS.remove(filename);
    else if (cmd == "status") {
       Serial.printf("Used: %lu / %lu bytes\n", SPIFFS.usedBytes(), SPIFFS.totalBytes());
    }
  }
}

void startLogging() {
  if (!isLogging) {
    Serial.println("\n>>> Logging START <<<\n");
    if (SPIFFS.exists(filename)) SPIFFS.remove(filename); 
    
    File flagFile = SPIFFS.open("/logging.flag", FILE_WRITE);
    flagFile.close();
    digitalWrite(ledPin, HIGH);
    isLogging = true;
  }
}

void stopLogging() {
  if (isLogging) {
    Serial.println("\n>>> Logging STOP <<<\n");
    SPIFFS.remove("/logging.flag");
    digitalWrite(ledPin, LOW);
    isLogging = false;
  }
}

// --- DUMP FILE TO SERIAL (USB) ---
void exportFileData() {
  File file = SPIFFS.open(filename, FILE_READ);
  if (!file) {
    Serial.println("No file to read.");
    return;
  }
  byte buffer[64];
  while(file.available()) {
    int bytesRead = file.read(buffer, sizeof(buffer));
    Serial.write(buffer, bytesRead); 
  }
  file.close();
}

// --- BLE EXPORT (Reliable ACK Mode) ---
void exportFileOverBLE() {
  stopLogging(); 
  
  File file = SPIFFS.open(filename, FILE_READ);
  if (!file) {
    Serial.println("No file to export.");
    return;
  }
  
  Serial.println("Starting BLE file export (Reliable ACK Mode)...");

  // 30 entries = 480 bytes (fits in 512 MTU)
  const int entriesPerPacket = 30; 
  byte buffer[sizeof(LogEntry) * entriesPerPacket]; 
  
  clientReadyForNextPacket = true; // Allow first packet

  while(file.available()) {
    unsigned long waitStartTime = millis();
    
    // --- 1. Wait for ACK from Client ---
    while (!clientReadyForNextPacket) {
        // Timeout check (3 seconds)
        if (millis() - waitStartTime > 3000) {
            Serial.println("ACK Timeout.");
            file.close();
            return;
        }
        delay(1); 
    }

    // --- 2. Read and Send Data ---
    int bytesRead = file.read(buffer, sizeof(buffer));
    if (bytesRead > 0) {
      // Lock the flag. It stays locked until onWrite receives "ACK"
      clientReadyForNextPacket = false; 
      
      pFileCharacteristic->setValue(buffer, bytesRead);
      pFileCharacteristic->notify(); 
    }
  }
  file.close();

  // --- 3. Finish Up ---
  delay(50); 
  pFileCharacteristic->setValue("END_OF_FILE");
  pFileCharacteristic->notify();
  Serial.println("Export complete.");
}

// --- LOGGING FUNCTION WITH AUTO-FULL DETECTION ---
void logIMUDataToFile() {
  // Check if memory is > 98% full
  if (SPIFFS.usedBytes() > (SPIFFS.totalBytes() * 0.025)) {
    Serial.println("!!! MEMORY FULL - AUTO EXPORT TRIGGERED !!!");
    stopLogging(); 
    
    // --- NEW: Notify the client that memory is full ---
    pCharacteristic->setValue("STATUS:FULL");
    pCharacteristic->notify();
    // --------------------------------------------------
    return;
  }

  inv_imu_sensor_event_t sensor_event; 
  if (IMU.getDataFromRegisters(sensor_event) != 0) return;

  LogEntry currentLog;
  
  // Apply Time Sync Offset
  currentLog.timestamp = millis() + timeOffset; 
  
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
}