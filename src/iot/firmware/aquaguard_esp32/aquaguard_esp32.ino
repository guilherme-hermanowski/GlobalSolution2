/*
 * AquaGuard / AlertaCidadão — Firmware de referência ESP32 (Arduino Core)
 * --------------------------------------------------------------------------
 * Hardware:
 *   - ESP32 DevKit V1
 *   - HC-SR04 (ultrassônico) instalado ACIMA do rio, apontando para a água
 *       TRIG -> GPIO 5 | ECHO -> GPIO 18 (use divisor de tensão 5V->3.3V no ECHO)
 *   - Sensor de chuva FC-37/YL-83 (módulo LM393)
 *       AO -> GPIO 34 (ADC1) | DO -> GPIO 35
 *   - LED de status -> GPIO 2 (onboard)
 * Simulação sem hardware: projeto equivalente no Wokwi (wokwi.com) ou use
 *   src/iot/simulator/iot_simulator.py, que envia o MESMO contrato JSON.
 * Bibliotecas: ArduinoJson (v7) — WiFi.h e HTTPClient.h já vêm no core ESP32.
 */
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ------------------------- CONFIGURAÇÃO -------------------------
const char* WIFI_SSID     = "SUA_REDE";
const char* WIFI_PASSWORD = "SUA_SENHA";
const char* API_URL       = "http://192.168.0.10:8000/api/telemetry"; // IP da máquina do backend
const char* DEVICE_TOKEN  = "fiap-gs-2026";                           // = DEVICE_TOKEN do .env
const char* DEVICE_ID     = "esp32-rio-01";

const float SENSOR_HEIGHT_CM = 500.0;  // altura do sensor em relação ao leito do rio
const float GEO_LAT = -23.5505, GEO_LON = -46.6333;   // generalizado no backend (LGPD)

const int PIN_TRIG = 5, PIN_ECHO = 18, PIN_RAIN_AO = 34, PIN_RAIN_DO = 35, PIN_LED = 2;

// Envio adaptativo: mais frequente quando o rio sobe (economia de energia/rede)
const unsigned long INTERVAL_NORMAL_MS = 30000;
const unsigned long INTERVAL_ALERT_MS  = 5000;
const float ALERT_LEVEL_CM = 250.0;

// Buffer offline (store-and-forward) — guarda leituras se o Wi-Fi/backend cair
const int BUFFER_SIZE = 20;
String offlineBuffer[BUFFER_SIZE];
int bufferCount = 0;

unsigned long lastSend = 0;

// ------------------------- SENSORES -------------------------
float readDistanceCm() {
  // Mediana de 5 leituras para filtrar ruído/ondas na superfície
  float samples[5];
  for (int i = 0; i < 5; i++) {
    digitalWrite(PIN_TRIG, LOW);  delayMicroseconds(2);
    digitalWrite(PIN_TRIG, HIGH); delayMicroseconds(10);
    digitalWrite(PIN_TRIG, LOW);
    long duration = pulseIn(PIN_ECHO, HIGH, 30000);          // timeout 30 ms (~5 m)
    samples[i] = duration > 0 ? duration * 0.0343 / 2.0 : -1;
    delay(60);
  }
  // ordenação simples (insertion sort) para obter a mediana
  for (int i = 1; i < 5; i++) { float k = samples[i]; int j = i - 1;
    while (j >= 0 && samples[j] > k) { samples[j + 1] = samples[j]; j--; } samples[j + 1] = k; }
  return samples[2];
}

float readRiverLevelCm() {
  float d = readDistanceCm();
  if (d < 0) return -1;                         // falha de leitura
  float level = SENSOR_HEIGHT_CM - d;           // nível = altura do sensor - distância até a água
  return constrain(level, 0, 1000);
}

float readRainIntensity() {
  int raw = analogRead(PIN_RAIN_AO);            // 0 (molhado) .. 4095 (seco)
  return constrain(map(raw, 4095, 0, 0, 100), 0, 100);
}

// ------------------------- REDE -------------------------
void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 10000) delay(250);
}

bool postJson(const String& body) {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  http.begin(API_URL);
  http.setTimeout(5000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  int code = http.POST(body);
  if (code > 0) Serial.printf("[HTTP] %d %s\n", code, http.getString().c_str());
  else          Serial.printf("[HTTP] erro: %s\n", http.errorToString(code).c_str());
  http.end();
  return code == 201;
}

void flushBuffer() {
  while (bufferCount > 0 && postJson(offlineBuffer[0])) {
    for (int i = 1; i < bufferCount; i++) offlineBuffer[i - 1] = offlineBuffer[i];
    bufferCount--;
  }
}

// ------------------------- CICLO -------------------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT); pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_RAIN_DO, INPUT); pinMode(PIN_LED, OUTPUT);
  analogReadResolution(12);
  ensureWiFi();
  Serial.println("AquaGuard ESP32 iniciado");
}

void loop() {
  float level = readRiverLevelCm();
  unsigned long interval = (level >= ALERT_LEVEL_CM) ? INTERVAL_ALERT_MS : INTERVAL_NORMAL_MS;
  if (millis() - lastSend < interval) { delay(200); return; }
  lastSend = millis();

  if (level < 0) { Serial.println("[SENSOR] leitura ultrassônica inválida — descartada"); return; }

  float rain = readRainIntensity();
  bool rainDetected = digitalRead(PIN_RAIN_DO) == LOW;   // LM393: LOW = molhado

  JsonDocument doc;
  doc["device_id"]      = DEVICE_ID;
  doc["river_level_cm"] = level;
  doc["rain_intensity"] = rain;
  doc["rain_detected"]  = rainDetected;
  doc["battery_v"]      = 3.7;           // substituir por leitura real do divisor da bateria
  doc["rssi"]           = WiFi.RSSI();
  doc["lat"] = GEO_LAT; doc["lon"] = GEO_LON;
  doc["source"]         = "real";
  String body; serializeJson(doc, body);

  digitalWrite(PIN_LED, level >= ALERT_LEVEL_CM);   // alerta visual local (edge)
  ensureWiFi();
  flushBuffer();
  if (!postJson(body) && bufferCount < BUFFER_SIZE) {
    offlineBuffer[bufferCount++] = body;            // store-and-forward
    Serial.printf("[BUFFER] %d leituras pendentes\n", bufferCount);
  }
}
