/*
 * AquaGuard / AlertaCidadão — Firmware de referência ESP32 (Arduino Core)
 * --------------------------------------------------------------------------
 * Hardware:
 *   - ESP32 DevKit V1
 *   - HC-SR04 (ultrassônico) instalado ACIMA do rio, apontando para a água
 *       TRIG -> GPIO 5 | ECHO -> GPIO 18 (use divisor de tensão 5V->3.3V no ECHO)
 *   - Sensor de chuva FC-37/YL-83 (módulo LM393), só a saída analógica (AO)
 *       AO -> GPIO 34 (ADC1) — rain_detected é derivado de rain_intensity no código
 * Simulação sem hardware: abra este firmware no Wokwi (wokwi.com) junto com
 *   diagram.json desta mesma pasta — HC-SR04 simula o rio, potenciômetro
 *   simula o sensor de chuva. A rede "Wokwi-GUEST" tem acesso real à
 *   internet de dentro do simulador, então o MQTT publica de verdade no
 *   HiveMQ Cloud (veja libraries.txt para as libs do projeto).
 * Publica via MQTT (TLS) no HiveMQ Cloud — o backend assina o mesmo tópico em
 *   app/services/mqtt_listener.py. Credenciais em secrets.h (gitignored);
 *   copie secrets.example.h e preencha antes de compilar.
 * Bibliotecas: PubSubClient, ArduinoJson (v7) — WiFi.h e WiFiClientSecure.h já
 *   vêm no core ESP32.
 */
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#include "secrets.h"

// ------------------------- CONFIGURAÇÃO -------------------------
// No Wokwi, mantenha "Wokwi-GUEST" (rede virtual com internet real). Num
// ESP32 físico, troque pela rede Wi-Fi real do local de instalação.
const char* WIFI_SSID     = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";
const char* MQTT_TOPIC    = "esp32/aquaguard/data";  // = MQTT_TOPIC do .env do backend
const char* DEVICE_ID     = "esp32-rio-01";

const float SENSOR_HEIGHT_CM = 500.0;  // altura do sensor em relação ao leito do rio
const float GEO_LAT = -23.5505, GEO_LON = -46.6333;   // generalizado no backend (LGPD)

const int PIN_TRIG = 5, PIN_ECHO = 18, PIN_RAIN_AO = 34;
const float RAIN_DETECTED_THRESHOLD = 10.0;  // mesmo corte usado no backend (telemetry.py)

// Envio adaptativo: mais frequente quando o rio sobe (economia de energia/rede)
const unsigned long INTERVAL_NORMAL_MS = 30000;
const unsigned long INTERVAL_ALERT_MS  = 5000;
const float ALERT_LEVEL_CM = 250.0;

// Buffer offline (store-and-forward) — guarda leituras se o Wi-Fi/backend cair
const int BUFFER_SIZE = 20;
String offlineBuffer[BUFFER_SIZE];
int bufferCount = 0;

unsigned long lastSend = 0;

WiFiClientSecure secureClient;
PubSubClient mqttClient(secureClient);

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

bool ensureMqtt() {
  if (mqttClient.connected()) return true;
  Serial.print("Conectando ao broker MQTT...");
  if (mqttClient.connect(DEVICE_ID, MQTT_USER, MQTT_PASSWORD)) {
    Serial.println(" conectado.");
    return true;
  }
  Serial.printf(" falhou, rc=%d\n", mqttClient.state());
  return false;
}

bool publishJson(const String& body) {
  if (WiFi.status() != WL_CONNECTED || !ensureMqtt()) return false;
  bool ok = mqttClient.publish(MQTT_TOPIC, body.c_str());
  Serial.printf("[MQTT] %s -> %s\n", ok ? "publicado" : "falhou", body.c_str());
  return ok;
}

void flushBuffer() {
  while (bufferCount > 0 && publishJson(offlineBuffer[0])) {
    for (int i = 1; i < bufferCount; i++) offlineBuffer[i - 1] = offlineBuffer[i];
    bufferCount--;
  }
}

// ------------------------- CICLO -------------------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT); pinMode(PIN_ECHO, INPUT);
  analogReadResolution(12);
  ensureWiFi();
  secureClient.setInsecure();  // HiveMQ Cloud: pula a validação da cadeia de certificado (ok p/ projeto acadêmico)
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  Serial.println("AquaGuard ESP32 iniciado");
}

void loop() {
  mqttClient.loop();
  float level = readRiverLevelCm();
  unsigned long interval = (level >= ALERT_LEVEL_CM) ? INTERVAL_ALERT_MS : INTERVAL_NORMAL_MS;
  if (millis() - lastSend < interval) { delay(200); return; }
  lastSend = millis();

  if (level < 0) { Serial.println("[SENSOR] leitura ultrassônica inválida — descartada"); return; }

  float rain = readRainIntensity();
  bool rainDetected = rain > RAIN_DETECTED_THRESHOLD;

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

  ensureWiFi();
  flushBuffer();
  if (!publishJson(body) && bufferCount < BUFFER_SIZE) {
    offlineBuffer[bufferCount++] = body;            // store-and-forward
    Serial.printf("[BUFFER] %d leituras pendentes\n", bufferCount);
  }
}
