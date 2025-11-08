#include <Wire.h>
#include <math.h>
#include "ICM42670P.h"
#include "FS.h"
#include "SPIFFS.h"
#include <WiFi.h>
#include <WebServer.h>

// Wifi link: http://192.168.4.1.


struct LogEntry {
  unsigned long timestamp; // 4 bytes
  int16_t ax, ay, az;      // 2 bytes each (6 total)
  int16_t gx, gy, gz;      // 2 bytes each (6 total)
};

// --- WiFi & Web Server ---
const char* ssid = "IMU_LOGGER_AP";
WebServer server(80);

// Instantiate IMU
ICM42670 IMU(Wire, 0);

// File name for stored data
const char* filename = "/imu_data.bin";

// Timer control
unsigned long lastLogTime = 0;
const unsigned long logInterval = 25; // ms

// LED control
const int ledPin = 7;
bool isLogging = false;

void setup() {
  Serial.begin(115200);
  delay(2000);
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW);

  Serial.println("\n--- IMU Data Logger ---");
  Serial.println("Type 'start', 'stop', 'export', 'clear', 'status'");
  Serial.println("-------------------------");

  Serial.println("Initializing SPIFFS...");
  if (!SPIFFS.begin(true)) {
    Serial.println("!! SPIFFS Mount Failed !!");
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
    while (1);
  }
  Serial.println("IMU Initialized.");

  // --- Start WiFi Access Point ---
  Serial.println("\nStarting WiFi Access Point...");
  WiFi.softAP(ssid);
  IPAddress IP = WiFi.softAPIP();
  Serial.print("AP IP address: ");
  Serial.println(IP);
  Serial.println("Connect to WiFi: IMU_LOGGER_AP and visit http://" + IP.toString());

  // --- Web Server Routes ---
  server.on("/", handleRoot);
  server.on("/data", handleDownload);
  server.begin();
  Serial.println("Web server started.");

  IMU.startAccel(50, 2);
  IMU.startGyro(50, 250);

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
  server.handleClient();  // Handle WiFi connections
  checkSerialCommands();

  if (isLogging && (millis() - lastLogTime >= logInterval)) {
    lastLogTime = millis();
    logIMUData();
  }
}

// --- Webpage handlers ---
void handleRoot() {
  if (!SPIFFS.exists(filename)) {
    server.send(200, "text/html",
      "<html><body><h1>IMU Logger</h1><p>No data file found. Please log some data first.</p></body></html>");
    return;
  }

  File file = SPIFFS.open(filename, FILE_READ);
  size_t fileSize = file.size();
  file.close();

  String html = "<html><body><h1>IMU Logger</h1>";
  html += "<p>Data file found (" + String(fileSize) + " bytes).</p>";
  html += "<a href='/data'><button style='font-size:18px;padding:10px 20px;'>Download imu_data.bin</button></a>";
  html += "<p><small>Binary format (each record = 16 bytes)</small></p>";
  html += "</body></html>";

  server.send(200, "text/html", html);
}

void handleDownload() {
  if (!SPIFFS.exists(filename)) {
    server.send(404, "text/plain", "File not found.");
    return;
  }

  File file = SPIFFS.open(filename, FILE_READ);
  if (!file) {
    server.send(500, "text/plain", "Failed to open file.");
    return;
  }

  server.sendHeader("Content-Disposition", "attachment; filename=imu_data.bin");
  server.sendHeader("Content-Type", "application/octet-stream");
  server.sendHeader("Connection", "close");
  server.streamFile(file, "application/octet-stream");
  file.close();
}

// --- Serial Commands ---
void checkSerialCommands() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "start") {
      if (!isLogging) {
        Serial.println("\n>>> Logging START <<<\n");
        File flagFile = SPIFFS.open("/logging.flag", FILE_WRITE);
        flagFile.close();
        digitalWrite(ledPin, HIGH);
        isLogging = true;
      } else Serial.println("Already logging.");
    } 
    else if (cmd == "stop") {
      if (isLogging) {
        Serial.println("\n>>> Logging STOP <<<\n");
        SPIFFS.remove("/logging.flag");
        digitalWrite(ledPin, LOW);
        isLogging = false;
      } else Serial.println("Already stopped.");
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

// --- Logging ---
void logIMUData() {
  if (SPIFFS.usedBytes() > (SPIFFS.totalBytes() * 0.95)) {
    Serial.println("WARNING: Memory almost full! Deleting old log...");
    SPIFFS.remove(filename);
  }

  inv_imu_sensor_event_t sensor_event;
  int status = IMU.getDataFromRegisters(sensor_event);
  if (status != 0) {
    Serial.print("IMU read error: "); Serial.println(status);
    return;
  }

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

  Serial.printf("Logged: t=%lu ms\n", currentLog.timestamp);
}
