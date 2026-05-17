// --- BLE Includes ---
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>

// --- IMU & File System Includes ---
#include <Wire.h>     
#include <math.h>
#include "FS.h"
#include "SPIFFS.h"

// --- BLE Definitions ---
#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8" 
#define FILE_TRANSFER_CHAR_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a9"

BLECharacteristic *pCharacteristic;
BLECharacteristic *pFileCharacteristic; 

// --- IMU Definitions ---
#define IMU_ADDRESS   0x68   
#define WHO_AM_I_REG  0x75   
#define PWR_MGMT0_REG 0x1F   
#define ACCEL_DATA_START 0x0B 

// --- Global Variables ---
unsigned long timeOffset = 0;
volatile bool ackReceived = false; 

// --- NEW FLAGS FOR THREAD SAFETY ---
bool shouldExport = false; 
bool shouldStop = false;
bool shouldStart = false;

struct LogEntry {
  unsigned long timestamp; 
  int16_t ax, ay, az;      
  int16_t gx, gy, gz;      
};
const char* filename = "/imu_data.bin"; 

// --- Timer Control ---
unsigned long lastLogTime = 0;
const unsigned long logInterval = 25; 

// --- Control Flags ---
const int ledPin = 7;
bool isLogging = false;

// --- Function Prototypes (FIXED: Added missing declarations) ---
void startLogging();
void stopLogging();
void exportFileOverBLE(); 
void checkSerialCommands(); // Added
void logIMUDataToFile();    // Added

// --- CUSTOM LIBRARY FUNCTIONS ---
byte readI2CByte(byte reg) {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(reg);
  Wire.endTransmission(false); 
  Wire.requestFrom(IMU_ADDRESS, 1);
  return Wire.read();
}

void writeI2CByte(byte reg, byte val) {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

int my_imu_begin() {
  Wire.begin(10, 8); 
  Wire.setClock(50000L); 
  
  byte whoAmI = readI2CByte(WHO_AM_I_REG);
  Serial.print("IMU Who Am I? Read: 0x");
  Serial.println(whoAmI, HEX);

  if (whoAmI != 0x68 && whoAmI != 0x60) {
    Serial.println("IMU NOT found. Check wiring.");
    return -1;
  }
  
  Serial.println("IMU found. Waking up sensors...");
  writeI2CByte(PWR_MGMT0_REG, 0x0F);
  delay(10); 
  return 0; 
}

int my_imu_read(int16_t* data) {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(ACCEL_DATA_START); 
  Wire.endTransmission(false); 
  
  // Request 12 bytes ONLY (Assume no temperature gap)
  int bytesRead = Wire.requestFrom(IMU_ADDRESS, 12);
  
  if (bytesRead != 12) return -5; 

  data[0] = (Wire.read() << 8) | Wire.read(); // Accel X
  data[1] = (Wire.read() << 8) | Wire.read(); // Accel Y
  data[2] = (Wire.read() << 8) | Wire.read(); // Accel Z
  
  // REMOVED THE TEMP SKIP
  // int16_t temp = (Wire.read() << 8) | Wire.read(); 
  
  data[3] = (Wire.read() << 8) | Wire.read(); // Gyro X
  data[4] = (Wire.read() << 8) | Wire.read(); // Gyro Y
  data[5] = (Wire.read() << 8) | Wire.read(); // Gyro Z
  
  return 0;
}

// --- BLE Callback Class ---
class MyCallbacks: public BLECharacteristicCallbacks {
   void onWrite(BLECharacteristic *pCharacteristic) {
      String value = pCharacteristic->getValue();
      if (value.length() > 0) {
        Serial.print("BLE received: ");
        Serial.println(value);

        // USE FLAGS ONLY - NO HEAVY LOGIC HERE
        if (value == "start") {
           shouldStart = true;
        } else if (value == "stop") {
           shouldStop = true;
        } else if (value == "export_ble") { 
           shouldExport = true; // Sets flag for main loop
        } else if (value.startsWith("TIME:")) {
           String timeStr = value.substring(5);
           unsigned long pcTime = strtoul(timeStr.c_str(), NULL, 10);
           timeOffset = pcTime - millis();
           Serial.print("Time Synced. Offset: ");
           Serial.println(timeOffset);
        } else if (value == "ACK") {
           ackReceived = true; // This will now work because main loop handles the wait
        }
      }
  }
};

void setup() {
  Serial.begin(115200);
  delay(2000);
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW);

  Serial.println("\n--- IMU Data Logger + Custom BLE (Wrist) ---");

  if (!SPIFFS.begin(true)) {
    Serial.println("!! SPIFFS Mount Failed !!");
    while (1); 
  }

  int status = my_imu_begin(); 
  if (status != 0) {
    Serial.print("IMU init failed: "); Serial.println(status);
    while (1); 
  }
  Serial.println("IMU Initialized.");

  Serial.println("Starting BLE server...");
  BLEDevice::init("My_ESP32_IMU_Wrist_Trial"); 
  BLEServer *pServer = BLEDevice::createServer();
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
  BLEDevice::startAdvertising();
  Serial.println("BLE Server started. Advertising...");
  
  if (SPIFFS.exists("/logging.flag")) {
    isLogging = true;
    digitalWrite(ledPin, HIGH);
  }
}

void loop() {
  // --- FLAG HANDLERS (MAIN THREAD) ---
  if (shouldStart) {
      startLogging();
      shouldStart = false;
  }
  if (shouldStop) {
      stopLogging();
      shouldStop = false;
  }
  if (shouldExport) {
      exportFileOverBLE(); 
      shouldExport = false;
  }

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
    if (cmd == "start") shouldStart = true;
    else if (cmd == "stop") shouldStop = true;
    else if (cmd == "export_ble") shouldExport = true;
    else if (cmd == "clear") {
      Serial.println("\n!!! FORMATTING FILESYSTEM !!!");
      SPIFFS.format();
      Serial.println("Please RESTART.");
      while (1);
    }
    else if (cmd == "status") {
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

void exportFileOverBLE() {
    stopLogging(); 

    File file = SPIFFS.open(filename, FILE_READ);
    if (!file) {
        Serial.println("Failed to open file for BLE export");
        return;
    }

    Serial.println("Starting Robust BLE export...");

    const int CHUNK_SIZE = 20; 
    byte buffer[CHUNK_SIZE];
    int packetCounter = 0; 

    while(file.available()) {
        int bytesRead = file.read(buffer, CHUNK_SIZE);
        
        if (bytesRead > 0) {
            pFileCharacteristic->setValue(buffer, bytesRead);
            pFileCharacteristic->notify();
            
            packetCounter++;

            if (packetCounter >= 5) {
                ackReceived = false; 
                unsigned long startTime = millis();
                
                while (!ackReceived && (millis() - startTime < 1500)) {
                    delay(1); 
                }

                if (!ackReceived) {
                    Serial.println("ACK Timeout! Continuing...");
                }
                
                packetCounter = 0; 
            } else {
                delay(5); 
            }
        }
    }

    file.close();
    delay(50);
    pFileCharacteristic->setValue("END_OF_FILE");
    pFileCharacteristic->notify();
    Serial.println("BLE file export complete.");
}

int16_t sensor_data[6]; 

void logIMUDataToFile() {
  if (SPIFFS.usedBytes() > (SPIFFS.totalBytes() * 0.98)) {
    Serial.println("!!! MEMORY FULL !!!");
    stopLogging(); 
    return;        
  }

  int status = my_imu_read(sensor_data);
  if (status != 0) return;

  LogEntry currentLog;
  currentLog.timestamp = millis() + timeOffset; 
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
}
