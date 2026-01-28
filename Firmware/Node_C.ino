/*
 * NODE C - FINAL STABLE
 * No WiFi switching (Floating ESP32 handles interference)
 */

#include "esp_task_wdt.h"
#include <PubSubClient.h>
#include <WiFi.h>
#include <math.h>

#define WDT_TIMEOUT 15 // Watchdog timeout in seconds

const char *ssid = "StampedeShield";
const char *password = "8667220245";
const char *mqtt_server = "broker.hivemq.com";

#define TRIG_PIN 12
#define ECHO_PIN 14
#define PIR_PIN 13
#define MIC_PIN 34
#define GREEN_LED 32
#define YELLOW_LED 27
#define RED_LED 26
#define BUZZER_PIN 25

WiFiClient espClient;
PubSubClient client(espClient);

int micBaseline = 0;
String currentAlert = "SAFE";
unsigned long lastHeartbeat = 0; // For health monitoring

// PIR debounce variables
bool lastPirState = false;
unsigned long pirChangeTime = 0;
bool debouncedPir = false;

// MQTT Callback
void callback(char *topic, byte *payload, unsigned int length) {
  String msg = "";
  for (int i = 0; i < length; i++)
    msg += (char)payload[i];
  currentAlert = msg;
}

void setup() {
  Serial.begin(115200);

  // Initialize watchdog timer
  esp_task_wdt_init(WDT_TIMEOUT, true);
  esp_task_wdt_add(NULL);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(PIR_PIN, INPUT);
  pinMode(MIC_PIN, INPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);

  // Calibrate
  long sum = 0;
  for (int i = 0; i < 20; i++) {
    sum += analogRead(MIC_PIN);
    delay(10);
  }
  micBaseline = sum / 20;

  // Connect WiFi with timeout
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int wifiAttempts = 0;
  while (WiFi.status() != WL_CONNECTED &&
         wifiAttempts < 40) { // 20 second timeout
    delay(500);
    Serial.print(".");
    wifiAttempts++;
    esp_task_wdt_reset(); // Keep watchdog happy during connection
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n❌ WiFi Failed - Restarting...");
    delay(1000);
    ESP.restart(); // Reboot instead of hanging forever
  }

  Serial.println("\n✅ WiFi Connected");

  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

void reconnect() {
  int attempts = 0;
  while (!client.connected() && attempts < 10) {
    String id = "NodeC_" + String(random(0xffff), HEX);
    if (client.connect(id.c_str())) {
      client.subscribe("stampede/commands");
      return;
    } else {
      attempts++;
      delay(1000);
      esp_task_wdt_reset(); // Keep watchdog happy
    }
  }

  if (!client.connected()) {
    Serial.println("❌ MQTT Failed - Restarting...");
    ESP.restart();
  }
}

// Calculate RMS (Root Mean Square) audio level
// Takes 50 samples over ~10ms for stable reading
int readMicRMS() {
  long sumSquares = 0;
  for (int i = 0; i < 50; i++) {
    int sample = analogRead(MIC_PIN) - micBaseline;
    sumSquares += (long)sample * sample;
    delayMicroseconds(200); // ~10ms total for 50 samples
  }
  return (int)sqrt(sumSquares / 50.0);
}

float getDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 25000);
  if (duration > 0)
    return duration * 0.034 / 2.0;
  return -1;
}

void loop() {
  esp_task_wdt_reset(); // Feed the watchdog

  if (!client.connected())
    reconnect();
  client.loop();

  // Read Sensors
  float dist = getDistance();
  int mic = readMicRMS(); // RMS for stable audio level

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

  // Use last good distance if fail
  static float lastDist = 100.0;
  if (dist > 0)
    lastDist = dist;

  // Send Data
  String p = "{\"id\":\"NODE_C\",\"dist\":";
  p += String(lastDist, 1);
  p += ",\"pir\":";
  p += String(pir);
  p += ",\"mic\":";
  p += String(mic);
  p += "}";

  client.publish("stampede/data", p.c_str());
  Serial.println(p);

  // Update LEDs based on Command
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  if (currentAlert == "CRITICAL") {
    digitalWrite(RED_LED, HIGH);
    digitalWrite(BUZZER_PIN, HIGH);
    delay(100);
    digitalWrite(BUZZER_PIN, LOW);
  } else if (currentAlert == "HIGH") {
    digitalWrite(RED_LED, HIGH);
  } else if (currentAlert == "MODERATE") {
    digitalWrite(YELLOW_LED, HIGH);
  } else {
    digitalWrite(GREEN_LED, HIGH);
  }

  // Send heartbeat every 10 seconds
  if (millis() - lastHeartbeat > 10000) {
    String hb = "{\"type\":\"heartbeat\",\"id\":\"NODE_C\",\"uptime\":";
    hb += String(millis() / 1000);
    hb += "}";
    client.publish("stampede/health", hb.c_str());
    lastHeartbeat = millis();
  }

  delay(500);
}