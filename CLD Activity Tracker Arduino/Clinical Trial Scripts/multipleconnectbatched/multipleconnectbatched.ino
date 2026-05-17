// --- BLE Includes ---
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>
#include "esp_mac.h" // Required for Unique ID

// --- IMU & File System Includes ---
#include <Wire.h> 
#include <math.h>
#include <ICM42670P.h>
#include "FS.h"
#include "SPIFFS.h"
#include <vector> 

ICM42670 IMU(Wire, 0);

// --- BLE Definitions ---
#define SERVICE_UUID            "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID     "beb5483e-36e1-4688-b7f5-ea07361b26a8" 
#define FILE_TRANSFER_CHAR_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a9"

BLECharacteristic *pCharacteristic;
BLECharacteristic *pFileCharacteristic; 

// --- IMU Definitions ---
struct LogEntry {
  unsigned long timestamp; 
  int16_t ax, ay, az;      
  int16_t gx, gy, gz;      
}; 
const char* filename = "/imu_data.bin"; 

// --- Timer Control ---
unsigned long lastLogTime = 0;
const unsigned long logInterval = 25; // 25ms = 40Hz Target

// --- Control Flags ---
const int ledPin = 7; // Adjust for your board (often 8 or 10 on C3 mini)
bool isLogging = false;
volatile bool clientReadyForNextPacket = false; 
unsigned long timeOffset = 0; 
bool statusSent = false; 

// --- BUFFERS ---

// 1. RAM LIFEBOAT (For Export)
const int MAX_RAM_ENTRIES = 2000; // Reduced slightly for safety
std::vector<LogEntry> ramBuffer; 
bool isExporting = false; 

// 2. DISK WRITE BUFFER (For Logging)
// INCREASED TO 100 to fix "Lazy Device" / Flash Latency issues
std::vector<LogEntry> logBatch; 
const int WRITE_BATCH_SIZE = 100; // Stores 2.5 seconds of data before writing

// --- Function Prototypes ---
void startLogging();
void stopLogging();
void exportFileData(); 
void exportFileOverBLE(); 
void logIMUDataToFile();
void captureSensorDataToRAM(); 

// --- Connection Watcher (Instant Reconnect Fix) ---
class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      Serial.println("Device Connected!");
    }

    void onDisconnect(BLEServer* pServer) {
      Serial.println("Device Disconnected... Restarting Advertising.");
      delay(500); 
      pServer->startAdvertising(); // Auto-restart advertising
    }
};

// --- BLE Callback Class ---
class MyCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      String value = pCharacteristic->getValue();
      if (value.length() > 0) {
        
        if (value == "ACK") {
          clientReadyForNextPacket = true;
          return; 
        }

        Serial.print("BLE received: ");
        Serial.println(value);
        
        if (value == "start") {
          startLogging();
        } else if (value == "stop") {
          stopLogging();
        } else if (value == "export") { 
           stopLogging();
           exportFileData(); 
        } else if (value == "export_ble") { 
          exportFileOverBLE();
        } else if (value.startsWith("TIME:")) {
          String timeStr = value.substring(5);
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

  Serial.println("\n--- Continuous Logging System (Optimized 100-Batch) ---");

  // Reserve memory to prevent heap fragmentation
  ramBuffer.reserve(1000); 
  logBatch.reserve(200); // Reserve for larger batch

  if (!SPIFFS.begin(true)) {
    Serial.println("!! SPIFFS Mount Failed !!");
    while (1); 
  }

  Serial.printf("Total Disk Space: %lu bytes\n", SPIFFS.totalBytes());
  Serial.printf("Used Disk Space:  %lu bytes\n", SPIFFS.usedBytes());

  Wire.begin(10, 8); 
  if (IMU.begin() != 0) { 
    Serial.println("IMU init failed!");
    while (1);
  }
  IMU.startAccel(50, 2); 
  IMU.startGyro(50, 250); 
  
  // --- Unique Name Generation ---
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA); 
  char name[30];
  sprintf(name, "IMU_%02X%02X", mac[4], mac[5]); 
  Serial.print("Device Name: "); Serial.println(name);
  
  BLEDevice::init(name);
  BLEDevice::setMTU(517); 
  BLEDevice::setPower(ESP_PWR_LVL_P9, ESP_BLE_PWR_TYPE_ADV); 
  
  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks()); // Add Instant Reconnect
  
  BLEService *pService = pServer->createService(SERVICE_UUID);

  pCharacteristic = pService->createCharacteristic(
                                CHARACTERISTIC_UUID,
                                BLECharacteristic::PROPERTY_READ |
                                BLECharacteristic::PROPERTY_WRITE |
                                BLECharacteristic::PROPERTY_NOTIFY
                              );
  pCharacteristic->addDescriptor(new BLE2902());
  pCharacteristic->setCallbacks(new MyCallbacks()); 
  pCharacteristic->setValue("IMU Ready");
  
  pFileCharacteristic = pService->createCharacteristic(
                                FILE_TRANSFER_CHAR_UUID,
                                BLECharacteristic::PROPERTY_NOTIFY
                              );
  pFileCharacteristic->addDescriptor(new BLE2902());
  
  pService->start();
  
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  
  // "Polite" Advertising (Comment out if connection is hard to find)
  // pAdvertising->setMinPreferred(0x100); 
  // pAdvertising->setMinPreferred(0x200); 
  
  BLEDevice::startAdvertising();
  
  // Looser params for multi-device stability
  pServer->updateConnParams(pServer->getConnId(), 32, 48, 0, 400);
  
  Serial.println("BLE Ready.");
  
  // Resume logging if rebooted
  if (SPIFFS.exists("/logging.flag")) {
    isLogging = true;
    digitalWrite(ledPin, HIGH);
  }
}

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "start") startLogging();
    else if (cmd == "stop") stopLogging();
    else if (cmd == "export_ble") exportFileOverBLE();
    else if (cmd == "status") {
        Serial.printf("Used: %lu / %lu bytes\n", SPIFFS.usedBytes(), SPIFFS.totalBytes());
    }
  }

  // Normal Logging Loop
  if (isLogging && !isExporting && (millis() - lastLogTime >= logInterval)) {
    lastLogTime = millis();
    logIMUDataToFile(); 
  }
}

void startLogging() {
  if (!isLogging) {
    Serial.println("\n>>> Logging START <<<\n");
    if (SPIFFS.exists(filename)) SPIFFS.remove(filename); 
    statusSent = false; 
    ramBuffer.clear(); 
    logBatch.clear();
    
    File flagFile = SPIFFS.open("/logging.flag", FILE_WRITE);
    flagFile.close();
    digitalWrite(ledPin, HIGH);
    isLogging = true;
  }
}

void stopLogging() {
  if (isLogging) {
    Serial.println("\n>>> Logging STOP <<<\n");
    
    // --- FLUSH REMAINING DATA ---
    if (logBatch.size() > 0) {
       File file = SPIFFS.open(filename, FILE_APPEND);  
       if (file) {
         file.write((uint8_t*)logBatch.data(), logBatch.size() * sizeof(LogEntry)); 
         file.close();
         Serial.printf("Flushed final %d entries.\n", logBatch.size());
       }
       logBatch.clear();
    }
    // ----------------------------

    SPIFFS.remove("/logging.flag");
    digitalWrite(ledPin, LOW);
    isLogging = false;
  }
}

// --- Serial Export (Legacy) ---
void exportFileData() {
  File file = SPIFFS.open(filename, FILE_READ);
  if (!file) return;
  byte buffer[64];
  while(file.available()) {
    int bytesRead = file.read(buffer, sizeof(buffer));
    Serial.write(buffer, bytesRead); 
  }
  file.close();
}

// --- HELPER: Capture Sensor Data to RAM (Lifeboat) ---
void captureSensorDataToRAM() {
  if (millis() - lastLogTime >= logInterval) {
    lastLogTime = millis();
    if (ramBuffer.size() >= MAX_RAM_ENTRIES) return;

    inv_imu_sensor_event_t sensor_event; 
    if (IMU.getDataFromRegisters(sensor_event) == 0) {
        LogEntry entry;
        entry.timestamp = millis() + timeOffset; 
        entry.ax = sensor_event.accel[0]; 
        entry.ay = sensor_event.accel[1];  
        entry.az = sensor_event.accel[2];  
        entry.gx = sensor_event.gyro[0];  
        entry.gy = sensor_event.gyro[1];  
        entry.gz = sensor_event.gyro[2];  
        ramBuffer.push_back(entry);
    }
  }
}

// --- BLE EXPORT (Batched + Robust) ---
void exportFileOverBLE() {
  isExporting = true;
  
  File file = SPIFFS.open(filename, FILE_READ);
  if (!file) {
    Serial.println("No file.");
    isExporting = false;
    return;
  }
  
  Serial.println("Starting Batched Export...");

  const int entriesPerPacket = 18; // 288 Bytes (Safe for all OS)
  byte buffer[sizeof(LogEntry) * entriesPerPacket]; 
  
  int packetCount = 0;
  const int BATCH_SIZE = 50; // MUST MATCH WEBSITE JS
  
  clientReadyForNextPacket = true; 

  while(file.available()) {
    
    // 1. Wait for ACK (Every 50 packets)
    if (packetCount > 0 && packetCount % BATCH_SIZE == 0) {
        clientReadyForNextPacket = false; 
        unsigned long waitStart = millis();
        
        while (!clientReadyForNextPacket) {
            captureSensorDataToRAM(); 
            
            // Timeout 10s
            if (millis() - waitStart > 10000) {
                Serial.println("ACK Timeout - Connection Lost.");
                file.close();
                isExporting = false;
                return;
            }
            delay(1); 
        }
    }

    captureSensorDataToRAM(); 

    // 2. Read and Send
    int bytesRead = file.read(buffer, sizeof(buffer));
    if (bytesRead > 0) {
      pFileCharacteristic->setValue(buffer, bytesRead);
      pFileCharacteristic->notify(); 
      packetCount++;
      
      // PACING DELAY (35ms = Good for 2 devices)
      delay(35); 
    }
  }
  file.close();
  
  // --- FLUSH RAM ---
  Serial.printf("Flushing %d entries from RAM...\n", ramBuffer.size());
  captureSensorDataToRAM();
  SPIFFS.remove(filename);
  statusSent = false; 

  File newFile = SPIFFS.open(filename, FILE_APPEND);
  if (newFile) {
     int entriesToFlush = ramBuffer.size(); 
     int index = 0;
     const int CHUNK_SIZE = 40; 
     while (index < entriesToFlush) {
        int remaining = entriesToFlush - index;
        int toWrite = (remaining < CHUNK_SIZE) ? remaining : CHUNK_SIZE;
        newFile.write((uint8_t*)&ramBuffer[index], toWrite * sizeof(LogEntry));
        index += toWrite;
        captureSensorDataToRAM(); 
        delay(2);
     }
     newFile.close();
     if (entriesToFlush > 0) ramBuffer.erase(ramBuffer.begin(), ramBuffer.begin() + entriesToFlush);
  }
  
  isExporting = false; 

  // End Signal
  delay(100);
  pFileCharacteristic->setValue("END_OF_FILE");
  pFileCharacteristic->notify();
  Serial.println("Export complete. Logging Resumed.");
}

// --- LOGGING TO FILE (Batch Size 100 for Stability) ---
void logIMUDataToFile() {
  // 1. Check for Memory Full
  if (SPIFFS.usedBytes() > (SPIFFS.totalBytes() * 0.97)) {
    if (!statusSent) {
      Serial.println("!!! MEMORY FULL !!!");
      pCharacteristic->setValue("STATUS:FULL");
      pCharacteristic->notify();
      statusSent = true; 
    }
    return;
  }

  // 2. Read Sensor
  inv_imu_sensor_event_t sensor_event; 
  if (IMU.getDataFromRegisters(sensor_event) != 0) return;

  LogEntry currentLog;
  currentLog.timestamp = millis() + timeOffset; 
  currentLog.ax = sensor_event.accel[0]; 
  currentLog.ay = sensor_event.accel[1];  
  currentLog.az = sensor_event.accel[2];  
  currentLog.gx = sensor_event.gyro[0];  
  currentLog.gy = sensor_event.gyro[1];  
  currentLog.gz = sensor_event.gyro[2];  

  // 3. Add to Batch (RAM)
  logBatch.push_back(currentLog);

  // 4. Only Write to Disk when Batch is Full (100 Entries)
  if (logBatch.size() >= WRITE_BATCH_SIZE) {
      File file = SPIFFS.open(filename, FILE_APPEND);  
      if (file) {
        file.write((uint8_t*)logBatch.data(), logBatch.size() * sizeof(LogEntry)); 
        file.close();
      }
      logBatch.clear();
  }
}