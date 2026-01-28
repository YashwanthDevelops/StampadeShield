/*
 * NODE A - MQTT FIRMWARE
 */

#include "esp_task_wdt.h"
#include <PubSubClient.h>
#include <WiFi.h>

#define WDT_TIMEOUT 15 // Watchdog timeout in seconds

const char *NODE_ID = "NODE_A"; // <-- MUST BE NODE_B!

const char *ssid = "StampedeShield";
const char *password = "8667220245";
const char *mqtt_server = "broker.hivemq.com";

#define TRIG_PIN 12
#define ECHO_PIN 14
#define PIR_PIN 13

WiFiClient espClient;
PubSubClient client(espClient);

float lastGoodDistance = 150.0;
unsigned long lastHeartbeat = 0; // For health monitoring

// PIR debounce variables
bool lastPirState = false;
unsigned long pirChangeTime = 0;
bool debouncedPir = false;

void setup() {
  Serial.begin(115200);
  delay(2000);

  // Initialize watchdog timer
  esp_task_wdt_init(WDT_TIMEOUT, true);
  esp_task_wdt_add(NULL);

  Serial.println("=== NODE_A STARTING ===");

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(PIR_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int count = 0;
  while (WiFi.status() != WL_CONNECTED && count < 20) {
    delay(500);
    Serial.print(".");
    count++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("✅ IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("❌ WiFi Failed");
  }

  client.setServer(mqtt_server, 1883);
  Serial.println("=== NODE_A READY ===");
}

float readDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 25000);

  if (duration > 0) {
    float d = duration * 0.034 / 2.0;
    if (d > 2 && d < 400) {
      lastGoodDistance = d;
      return d;
    }
  }
  return lastGoodDistance;
}

void connectMQTT() {
  if (!client.connected()) {
    String id = "NodeB_" + String(random(0xffff), HEX);
    client.connect(id.c_str());
  }
}

void loop() {
  esp_task_wdt_reset(); // Feed the watchdog

  if (WiFi.status() != WL_CONNECTED) {
    WiFi.begin(ssid, password);
    delay(1000);
    return;
  }

  connectMQTT();

  float distance = readDistance();

  // Debounced PIR reading
  bool rawPir = digitalRead(PIR_PIN);
  if (rawPir != lastPirState) {
    pirChangeTime = millis();
    lastPirState = rawPir;
  }
  if (millis() - pirChangeTime > 200) { // 200ms debounce
    debouncedPir = rawPir;
  }
  bool pir = debouncedPir;

  if (client.connected()) {
    String payload = "{\"id\":\"NODE_A\", \"dist\":";
    payload += String(distance, 1);
    payload += ", \"pir\":";
    payload += String(pir ? 1 : 0);
    payload += "}";

    client.publish("stampede/data", payload.c_str());
    client.loop();

    Serial.print("✅ NODE_A D:");
  } else {
    Serial.print("❌ NODE_A D:");
  }

  Serial.print(distance, 1);
  Serial.print(" P:");
  Serial.println(pir ? "Y" : "N");

  // Send heartbeat every 10 seconds
  if (millis() - lastHeartbeat > 10000) {
    String hb = "{\"type\":\"heartbeat\",\"id\":\"NODE_A\",\"uptime\":";
    hb += String(millis() / 1000);
    hb += "}";
    client.publish("stampede/health", hb.c_str());
    lastHeartbeat = millis();
  }

  delay(500);
}