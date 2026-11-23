// ParkQ Gate Controller - ESP32 firmware
// Two QR readers + two servo barriers + 4 IR slot sensors + LEDs + buzzer.
// The loop never blocks: everything uses millis() timers so QR reading is
// not stalled while a barrier is open.
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include "pins.h"

#ifdef MINIMAL_DEMO
// Demo with nothing wired (env:minimal): the BOOT button (GPIO0) acts as slot sensor 1 (held = car present),
// GPIO2 (the blue LED on many ESP32 boards) acts as the green "barrier open" light, other slots read "free".
#undef PIN_LED_G
#define PIN_LED_G 2
#define PIN_BOOT_BTN 0
#endif

// Relative path on purpose: a bare "config.h" can match a header inside the ESP32 framework.
#if __has_include("../include/config.h")
#include "../include/config.h"
#else
#include "config.example.h"   // lets `pio run` build with no secrets present
#endif
#ifndef WIFI_SSID             // the check above can match a framework header named config.h
#include "config.example.h"
#endif

#ifndef QR_BAUD
#define QR_BAUD 9600
#endif

// ---- tunables ---------------------------------------------------------------
static const int      SERVO_CLOSED = 0;
static const int      SERVO_OPEN = 90;
static const uint32_t OPEN_HOLD_MS = 3000;         // barrier stays open
static const uint32_t POLL_MS = 1000;              // GET commands every 1 s
static const uint32_t SLOTS_HEARTBEAT_MS = 30000;  // POST slots at least every 30 s
static const uint32_t SLOTS_SCAN_MS = 100;         // read IR sensors
static const uint32_t WIFI_RETRY_MS = 5000;
static const uint32_t HTTP_TIMEOUT_MS = 4000;
static const size_t   QR_MAX_LEN = 512;
static const uint32_t BEEP_SHORT_MS = 150;
static const uint32_t BEEP_LONG_MS = 800;
static const uint32_t LED_MS = 1500;

// ---- gates ------------------------------------------------------------------
struct Gate {
  const char* name;       // "in" / "out" (same as the server's gate name)
  Servo servo;
  int servoPin;
  HardwareSerial* qr;
  String line;            // QR text being received
  uint32_t lastByteAt;    // millis() of the last received byte
  bool open;
  uint32_t closeAt;
};

static HardwareSerial qrOutSerial(1);
static Gate gates[2] = {
  {"in",  Servo(), PIN_SERVO_IN,  &Serial2,     "", 0, false, 0},
  {"out", Servo(), PIN_SERVO_OUT, &qrOutSerial, "", 0, false, 0},
};

static const int SLOT_PINS[4] = {PIN_SLOT1, PIN_SLOT2, PIN_SLOT3, PIN_SLOT4};
static int  lastSlots[4] = {-1, -1, -1, -1};   // -1 = never sent -> sends at boot
static uint32_t lastSlotsSent = 0, lastSlotsScan = 0, lastPoll = 0, lastWifiTry = 0;

// ---- LED / buzzer feedback (non-blocking) ------------------------------------
static uint32_t ledGreenOff = 0, ledRedOff = 0, buzzOff = 0;

static void feedback(bool ok) {
  uint32_t now = millis();
  digitalWrite(ok ? PIN_LED_G : PIN_LED_R, HIGH);
  (ok ? ledGreenOff : ledRedOff) = now + LED_MS;
  digitalWrite(PIN_BUZZER, HIGH);                  // HIGH = beep (NPN driver)
  buzzOff = now + (ok ? BEEP_SHORT_MS : BEEP_LONG_MS);
}

static void updateFeedback() {
  uint32_t now = millis();
  if (ledGreenOff && (int32_t)(now - ledGreenOff) >= 0) { digitalWrite(PIN_LED_G, LOW); ledGreenOff = 0; }
  if (ledRedOff   && (int32_t)(now - ledRedOff)   >= 0) { digitalWrite(PIN_LED_R, LOW); ledRedOff = 0; }
  if (buzzOff     && (int32_t)(now - buzzOff)     >= 0) { digitalWrite(PIN_BUZZER, LOW); buzzOff = 0; }
}

// ---- barrier -----------------------------------------------------------------
// Open a barrier for 3 s. The server also queues an OPEN command after a
// successful scan, so if it is already open we only extend the timer
// (no second beep).
static void openGate(Gate& g) {
  if (WiFi.status() != WL_CONNECTED) return;       // stay closed while offline
  if (!g.open) {
    g.servo.write(SERVO_OPEN);
    g.open = true;
    Serial.printf("barrier %s: OPEN\n", g.name);
    feedback(true);
  }
  g.closeAt = millis() + OPEN_HOLD_MS;
}

static void updateGates() {
  for (Gate& g : gates) {
    bool timeUp = g.open && (int32_t)(millis() - g.closeAt) >= 0;
    if (timeUp || (g.open && WiFi.status() != WL_CONNECTED)) {
      g.servo.write(SERVO_CLOSED);
      g.open = false;
    }
  }
}

// ---- HTTP helper ---------------------------------------------------------------
// Returns the HTTP status (<0 on error); the response body goes into `out`.
static int httpRequest(bool post, const String& path, const String& body, String& out) {
  String url = String(API_BASE) + path;
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.setReuse(true);      // keep the TCP/TLS connection open between requests: one handshake instead of one per poll
  static WiFiClientSecure secure;   // static so the connection outlives this call
  static WiFiClient plain;
  static bool secureReady = false;
  if (url.startsWith("https://")) {
    if (!secureReady) { secure.setInsecure(); secureReady = true; }   // DEMO ONLY: skips certificate check. Pin a CA cert for production.
    http.begin(secure, url);
  } else {
    http.begin(plain, url); // plain HTTP for a LAN server
  }
  int code;
  if (post) {
    http.addHeader("Content-Type", "application/json");
    code = http.POST(body);
  } else {
    code = http.GET();
  }
  if (code > 0) out = http.getString();
  http.end();
  return code;
}

// ---- server commands: GET /api/iot/{lot}/commands ------------------------------
static void pollCommands() {
  String out;
  int code = httpRequest(false, String("/api/iot/") + LOT_ID + "/commands?device_key=" + DEVICE_KEY, "", out);
  if (code != 200) { Serial.printf("commands: HTTP %d\n", code); return; }
  JsonDocument doc;
  if (deserializeJson(doc, out)) return;
  for (JsonObject c : doc.as<JsonArray>()) {
    if (strcmp(c["command"] | "", "OPEN") != 0) continue;
    const char* gate = c["gate"] | "";
    for (Gate& g : gates) if (strcmp(g.name, gate) == 0) openGate(g);
  }
}

// ---- QR scan: POST /api/gate/{lot}/{in|out}/scan -------------------------------
static void sendScan(Gate& g, const String& token) {
  JsonDocument req;
  req["token"] = token;
  String body, out;
  serializeJson(req, body);
  int code = httpRequest(true, String("/api/gate/") + LOT_ID + "/" + g.name + "/scan", body, out);
  bool ok = false;
  if (code == 200) {
    JsonDocument res;
    if (!deserializeJson(res, out)) ok = res["open"] | false;  // 200 + open:true = allowed
  }
  Serial.printf("scan %s: HTTP %d -> %s\n", g.name, code, ok ? "OPEN" : "DENIED");
  if (ok) openGate(g); else feedback(false);
}

// Collect characters until \r or \n, OR until the reader has been silent for
// QR_IDLE_MS with something in the buffer (readers with no line ending);
// empty lines are ignored.
static const uint32_t QR_IDLE_MS = 100;

static void finishQrLine(Gate& g) {
  g.line.trim();
  String token = g.line;
  g.line = "";
  if (token.length() > 0) sendScan(g, token);
}

static void readQr(Gate& g) {
  while (g.qr->available()) {
    char c = g.qr->read();
    g.lastByteAt = millis();
    if (c == '\r' || c == '\n') {
      finishQrLine(g);
    } else if (g.line.length() < QR_MAX_LEN) {
      g.line += c;
    }
  }
  if (g.line.length() > 0 && millis() - g.lastByteAt >= QR_IDLE_MS) finishQrLine(g);
}

// ---- slot sensors: POST /api/iot/{lot}/slots -----------------------------------
static bool sendSlots(const int* s) {
  JsonDocument req;
  req["device_key"] = DEVICE_KEY;
  JsonArray arr = req["slots"].to<JsonArray>();
  for (int i = 0; i < 4; i++) arr.add(s[i]);
  String body, out;
  serializeJson(req, body);
  int code = httpRequest(true, String("/api/iot/") + LOT_ID + "/slots", body, out);
  Serial.printf("slots: HTTP %d\n", code);
  return code == 200;
}

// Send when something changed, or every 30 s as a heartbeat.
// If the POST fails we keep the old values, so it is retried on the next scan.
static void checkSlots() {
  int cur[4];
  bool changed = false;
  for (int i = 0; i < 4; i++) {
#ifdef MINIMAL_DEMO
    cur[i] = (i == 0 && digitalRead(PIN_BOOT_BTN) == LOW) ? 1 : 0;
#else
    cur[i] = digitalRead(SLOT_PINS[i]) == LOW ? 1 : 0;  // LOW = car present
#endif
    if (cur[i] != lastSlots[i]) changed = true;
  }
  bool heartbeat = millis() - lastSlotsSent >= SLOTS_HEARTBEAT_MS;
  if (!changed && !heartbeat) return;
  static uint32_t lastTry = 0;
  if (lastTry && millis() - lastTry < 2000) return;   // back off 2 s after a failed POST
  lastTry = millis();
  if (sendSlots(cur)) {
    memcpy(lastSlots, cur, sizeof(cur));
    lastSlotsSent = millis();
    lastTry = 0;
  }
}

// ---- Wi-Fi ---------------------------------------------------------------------
static void keepWifi() {
  static bool wasUp = false;
  bool up = WiFi.status() == WL_CONNECTED;
  if (up != wasUp) {
    wasUp = up;
    if (up) Serial.printf("Wi-Fi: connected, IP %s\n", WiFi.localIP().toString().c_str());
    else Serial.println("Wi-Fi: lost");
  }
  if (up) return;
  if (millis() - lastWifiTry < WIFI_RETRY_MS) return;
  lastWifiTry = millis();
  Serial.println("Wi-Fi: (re)connecting...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

// ---- main ----------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_LED_G, LOW);
  digitalWrite(PIN_LED_R, LOW);
  digitalWrite(PIN_BUZZER, LOW);
  for (int p : SLOT_PINS) pinMode(p, INPUT);   // GPIO34-39: no pull-ups, the IR module drives the line
#ifdef MINIMAL_DEMO
  pinMode(PIN_BOOT_BTN, INPUT_PULLUP);
#endif

  for (Gate& g : gates) { g.servo.attach(g.servoPin); g.servo.write(SERVO_CLOSED); }
  Serial2.begin(QR_BAUD, SERIAL_8N1, PIN_QR_IN_RX, PIN_QR_IN_TX);
  qrOutSerial.begin(QR_BAUD, SERIAL_8N1, PIN_QR_OUT_RX, PIN_QR_OUT_TX);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  lastWifiTry = millis();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

void loop() {
  keepWifi();
  for (Gate& g : gates) readQr(g);
  updateGates();
  updateFeedback();

  if (WiFi.status() != WL_CONNECTED) return;
  uint32_t now = millis();
  if (now - lastPoll >= POLL_MS)            { lastPoll = now; pollCommands(); }
  if (now - lastSlotsScan >= SLOTS_SCAN_MS) { lastSlotsScan = now; checkSlots(); }
}
