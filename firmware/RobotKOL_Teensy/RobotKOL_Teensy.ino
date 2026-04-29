// RobotKOL_Teensy.ino
// Teensy 4.0 firmware iskeleti
// Rol: Pi 5'ten USB-Serial üzerinden komut al, gerçek zamanlı motor/servo
// kontrolü yap, encoder + ToF okuyup telemetri gönder.
//
// Kütüphaneler:
//   AccelStepper  — step motor hız/ivme profili
//   TMCStepper    — TMC2209 UART konfigürasyonu (akım, mikrostep)
//   PWMServo      — Teensy'de Servo'ya göre daha stabil
//   Wire          — PCA9548A + AS5600
//
// Not: VL53L1X (ToF) Teensy'de DEĞİL — Raspberry Pi'nin I2C bus'ına bağlı.
// Protokol: 03_pi_teensy_protokol.md

#include <Arduino.h>
#include <AccelStepper.h>
#include <TMCStepper.h>
#include <PWMServo.h>
#include <Wire.h>
#include <ArduinoJson.h>

// ---------- Pin haritası (02_pin_map.md ile birebir) ----------
constexpr uint8_t M1_STEP = 2,  M1_DIR = 3;
constexpr uint8_t M2_STEP = 4,  M2_DIR = 5;
constexpr uint8_t M3_STEP = 6,  M3_DIR = 9;
constexpr uint8_t M4_STEP = 10, M4_DIR = 11;
constexpr uint8_t EN_PIN  = 12;          // ortak, aktif-düşük

constexpr uint8_t SERVO1_PIN = 14;
constexpr uint8_t SERVO2_PIN = 15;

constexpr uint8_t PCA_ADDR   = 0x70;
constexpr uint8_t AS5600_ADDR = 0x36;
constexpr uint8_t ENC_CHANNELS[4] = {1, 2, 4, 6};  // fiziksel PCA kanallari, araliklar lehim boslugu icin bilerek birakildi

// TMC2209 UART
#define TMC_SERIAL Serial2
constexpr float R_SENSE = 0.11f;         // tipik breakout (modele göre değişir)
constexpr uint8_t TMC_ADDR[4] = {0b00, 0b01, 0b10, 0b11};

// --- Motor: Usongshine 17HS4401 + 2-stage compound planetary ---
//   Motor: 1.7A pik, 40 N·cm tutma, 200 step/tur
//   Gearbox: 28.4:1 (3D baskı) → eklem başı ~7.4 N·m gerçek tork
constexpr uint16_t MOTOR_STEPS_PER_REV = 200;
constexpr uint16_t MICROSTEPS = 16;
constexpr float    GEAR_RATIO = 28.4f;

// Microstep / eklem derecesi
//   200 × 16 × 28.4 / 360 = 252.44
constexpr float STEPS_PER_DEG =
    (MOTOR_STEPS_PER_REV * MICROSTEPS * GEAR_RATIO) / 360.0f;

// Derece <-> step dönüşüm yardımcıları
inline int32_t degToSteps(float deg)   { return (int32_t)(deg * STEPS_PER_DEG); }
inline float   stepsToDeg(int32_t stp) { return stp / STEPS_PER_DEG; }

// Eksen başına akım (mA RMS) — gearbox sayesinde düşük tutuldu
constexpr uint16_t RMS_CURRENT[4] = {
  700,   // J1 taban
  800,   // J2 omuz (en yüklü)
  700,   // J3 dirsek
  600,   // J4 ön kol
};

// Eksen başına hız/ivme (microstep/s, microstep/s^2)
// Yanındaki yorum eklem çıkışındaki hızın derece eşdeğeri
constexpr float MAX_SPEED[4] = {
  15000,  // J1 ~60 °/s
  10000,  // J2 ~40 °/s
  12000,  // J3 ~48 °/s
  18000,  // J4 ~72 °/s
};
constexpr float MAX_ACCEL[4] = {
  20000,  // J1
  15000,  // J2
  18000,  // J3
  24000,  // J4
};

// ---------- Global nesneler ----------
AccelStepper stepper[4] = {
  AccelStepper(AccelStepper::DRIVER, M1_STEP, M1_DIR),
  AccelStepper(AccelStepper::DRIVER, M2_STEP, M2_DIR),
  AccelStepper(AccelStepper::DRIVER, M3_STEP, M3_DIR),
  AccelStepper(AccelStepper::DRIVER, M4_STEP, M4_DIR),
};

TMC2209Stepper tmc[4] = {
  TMC2209Stepper(&TMC_SERIAL, R_SENSE, TMC_ADDR[0]),
  TMC2209Stepper(&TMC_SERIAL, R_SENSE, TMC_ADDR[1]),
  TMC2209Stepper(&TMC_SERIAL, R_SENSE, TMC_ADDR[2]),
  TMC2209Stepper(&TMC_SERIAL, R_SENSE, TMC_ADDR[3]),
};

PWMServo servo1, servo2;

// ---------- Durum ----------
struct JointState {
  int32_t target_steps = 0;
  uint16_t encoder_raw = 0;     // 0..4095
  float    encoder_deg = 0.0f;
};
JointState joint[4];

bool     motors_enabled = false;
uint32_t last_tlm_ms = 0;
uint32_t last_cmd_ms = 0;
constexpr uint32_t TLM_PERIOD_MS = 50;  // 20 Hz telemetri
constexpr uint32_t CMD_TIMEOUT_MS = 500;  // Pi/Xbox baglantisi koparsa motorlari serbest birak

// ---------- I2C mux ----------
inline void tcaSelect(uint8_t ch) {
  Wire.beginTransmission(PCA_ADDR);
  Wire.write(1 << ch);
  Wire.endTransmission();
}

inline void tcaDisableAll() {
  Wire.beginTransmission(PCA_ADDR);
  Wire.write(0);
  Wire.endTransmission();
}

bool i2cProbe(uint8_t addr) {
  for (int attempt = 0; attempt < 3; attempt++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) return true;
    delay(2);
  }
  return false;
}

// AS5600 ham açı okuma (0..4095)
bool as5600Read(uint8_t ch, uint16_t& raw_out) {
  tcaSelect(ch);
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(0x0C);                       // RAW ANGLE H
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(AS5600_ADDR, (uint8_t)2) != 2) return false;
  uint16_t hi = Wire.read();
  uint16_t lo = Wire.read();
  raw_out = ((hi & 0x0F) << 8) | lo;
  return true;
}

bool as5600ReadByte(uint8_t ch, uint8_t reg, uint8_t& value_out) {
  tcaSelect(ch);
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(AS5600_ADDR, (uint8_t)1) != 1) return false;
  value_out = Wire.read();
  return true;
}

bool as5600ReadWord(uint8_t ch, uint8_t reg, uint16_t& value_out) {
  tcaSelect(ch);
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(AS5600_ADDR, (uint8_t)2) != 2) return false;
  uint16_t hi = Wire.read();
  uint16_t lo = Wire.read();
  value_out = ((hi & 0x0F) << 8) | lo;
  return true;
}

void setMotorsEnabled(bool on) {
  motors_enabled = on;
  digitalWrite(EN_PIN, motors_enabled ? LOW : HIGH);  // aktif-dusuk
}

void sendI2CScan() {
  StaticJsonDocument<512> d;
  d["ack"] = true;
  d["msg"] = "scan_i2c";
  JsonArray seen = d.createNestedArray("seen");
  for (uint8_t addr = 1; addr < 127; addr++) {
    if (i2cProbe(addr)) seen.add(addr);
  }

  d["pca"] = false;
  for (JsonVariant v : seen) {
    if ((uint8_t)v.as<int>() == PCA_ADDR) {
      d["pca"] = true;
      break;
    }
  }

  JsonArray ch = d.createNestedArray("channels");
  JsonArray enc = d.createNestedArray("enc");
  for (int i = 0; i < 4; i++) {
    ch.add(ENC_CHANNELS[i]);
    uint16_t raw = 0;
    enc.add(as5600Read(ENC_CHANNELS[i], raw));
  }
  tcaDisableAll();
  serializeJson(d, Serial);
  Serial.println();
}

void sendDiag() {
  StaticJsonDocument<1024> d;
  d["ack"] = true;
  d["msg"] = "diag";
  d["t"] = millis();
  d["en"] = motors_enabled;
  d["cmd_age_ms"] = millis() - last_cmd_ms;
  JsonArray ch = d.createNestedArray("channels");
  JsonArray ok = d.createNestedArray("enc_ok");
  JsonArray raw = d.createNestedArray("enc_raw");
  JsonArray deg = d.createNestedArray("enc_deg");
  JsonArray agc = d.createNestedArray("enc_agc");
  JsonArray mag = d.createNestedArray("enc_mag");
  JsonArray md = d.createNestedArray("status_md");
  JsonArray ml = d.createNestedArray("status_ml");
  JsonArray mh = d.createNestedArray("status_mh");

  for (int i = 0; i < 4; i++) {
    const uint8_t channel = ENC_CHANNELS[i];
    ch.add(channel);

    uint16_t raw_angle = 0;
    uint8_t status = 0;
    uint8_t agc_value = 0;
    uint16_t magnitude = 0;

    const bool raw_ok = as5600Read(channel, raw_angle);
    const bool status_ok = as5600ReadByte(channel, 0x0B, status);
    const bool agc_ok = as5600ReadByte(channel, 0x1A, agc_value);
    const bool mag_ok = as5600ReadWord(channel, 0x1B, magnitude);
    const bool all_ok = raw_ok && status_ok && agc_ok && mag_ok;

    ok.add(all_ok);
    raw.add(raw_ok ? raw_angle : 0);
    deg.add(raw_ok ? raw_angle * (360.0f / 4096.0f) : 0.0f);
    agc.add(agc_ok ? agc_value : 0);
    mag.add(mag_ok ? magnitude : 0);
    md.add(status_ok ? ((status & 0x20) != 0) : false);
    ml.add(status_ok ? ((status & 0x10) != 0) : false);
    mh.add(status_ok ? ((status & 0x08) != 0) : false);
  }

  tcaDisableAll();
  serializeJson(d, Serial);
  Serial.println();
}

// ---------- Komut ayrıştırma (satır bazlı JSON) ----------
// Örn: {"cmd":"move","j":[1000,-500,0,0],"v":800,"a":1600}\n
//      {"cmd":"servo","s":[90,45]}\n
//      {"cmd":"en","on":1}\n
//      {"cmd":"home"}\n

constexpr size_t JSON_BUF = 512;
StaticJsonDocument<JSON_BUF> doc;
String lineBuf;

void sendAck(const char* msg, bool ok = true) {
  StaticJsonDocument<128> d;
  d["ack"] = ok;
  d["msg"] = msg;
  serializeJson(d, Serial);
  Serial.println();
}

void sendTelemetry() {
  StaticJsonDocument<512> d;
  d["t"] = millis();
  JsonArray enc = d.createNestedArray("enc_deg");     // AS5600 ölçümü
  JsonArray pos = d.createNestedArray("pos_steps");   // stepper hedef step
  JsonArray jdeg = d.createNestedArray("joint_deg");  // stepper pozisyonu derece
  for (int i = 0; i < 4; i++) {
    enc.add(joint[i].encoder_deg);
    long cur = stepper[i].currentPosition();
    pos.add(cur);
    jdeg.add(stepsToDeg(cur));
  }
  d["en"]     = motors_enabled;
  serializeJson(d, Serial);
  Serial.println();
}

void handleCommand(JsonDocument& d) {
  const char* cmd = d["cmd"] | "";
  last_cmd_ms = millis();
  if (strcmp(cmd, "move") == 0) {
    // Step cinsinden mutlak pozisyon
    JsonArray j = d["j"].as<JsonArray>();
    float v = d["v"] | 800.0f;
    float a = d["a"] | 1600.0f;
    for (int i = 0; i < 4 && i < (int)j.size(); i++) {
      stepper[i].setMaxSpeed(v);
      stepper[i].setAcceleration(a);
      stepper[i].moveTo((long)j[i]);
      joint[i].target_steps = (int32_t)j[i];
    }
    sendAck("move");
  } else if (strcmp(cmd, "move_deg") == 0) {
    // Derece cinsinden mutlak eklem açısı
    JsonArray j = d["j"].as<JsonArray>();
    for (int i = 0; i < 4 && i < (int)j.size(); i++) {
      int32_t s = degToSteps((float)j[i]);
      // Hız/ivme derece/s veriliyorsa step/s'ye çevir
      float vdeg = d["v"] | 0.0f;
      float adeg = d["a"] | 0.0f;
      if (vdeg > 0) stepper[i].setMaxSpeed(vdeg * STEPS_PER_DEG);
      if (adeg > 0) stepper[i].setAcceleration(adeg * STEPS_PER_DEG);
      stepper[i].moveTo(s);
      joint[i].target_steps = s;
    }
    sendAck("move_deg");
  } else if (strcmp(cmd, "servo") == 0) {
    JsonArray s = d["s"].as<JsonArray>();
    if (s.size() >= 1) servo1.write(constrain((int)s[0], 0, 180));
    if (s.size() >= 2) servo2.write(constrain((int)s[1], 0, 180));
    sendAck("servo");
  } else if (strcmp(cmd, "en") == 0) {
    setMotorsEnabled(((int)d["on"]) != 0);
    sendAck("en");
  } else if (strcmp(cmd, "stop") == 0) {
    for (int i = 0; i < 4; i++) stepper[i].stop();
    sendAck("stop");
  } else if (strcmp(cmd, "home") == 0) {
    // TODO: endstop + yavaş geri hareket + encoder sıfırlama
    for (int i = 0; i < 4; i++) stepper[i].setCurrentPosition(0);
    sendAck("home");
  } else if (strcmp(cmd, "ping") == 0) {
    sendAck("pong");
  } else if (strcmp(cmd, "scan_i2c") == 0) {
    sendI2CScan();
  } else if (strcmp(cmd, "diag") == 0) {
    sendDiag();
  } else {
    sendAck("unknown", false);
  }
}

void pollSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      doc.clear();
      DeserializationError err = deserializeJson(doc, lineBuf);
      if (!err) handleCommand(doc);
      else sendAck("parse_err", false);
      lineBuf = "";
    } else if (c != '\r') {
      lineBuf += c;
      if (lineBuf.length() > JSON_BUF) lineBuf = "";  // taşma koruması
    }
  }
}

// ---------- Setup ----------
void setup() {
  pinMode(EN_PIN, OUTPUT);
  setMotorsEnabled(false);                // başlangıçta motorlar serbest

  Serial.begin(115200);                   // USB-Serial (hız ignore on Teensy)
  while (!Serial && millis() < 2000) {}

  TMC_SERIAL.begin(115200);
  for (int i = 0; i < 4; i++) {
    tmc[i].begin();
    tmc[i].toff(4);
    tmc[i].rms_current(RMS_CURRENT[i]);   // eksen başına akım (mA RMS)
    tmc[i].microsteps(MICROSTEPS);
    tmc[i].pwm_autoscale(true);           // StealthChop otomatik ayarı
    tmc[i].en_spreadCycle(false);         // sessiz mod (StealthChop)
    stepper[i].setMaxSpeed(MAX_SPEED[i]);
    stepper[i].setAcceleration(MAX_ACCEL[i]);
  }

  Wire.begin();
  Wire.setClock(100000);

  servo1.attach(SERVO1_PIN);
  servo2.attach(SERVO2_PIN);
  servo1.write(90);
  servo2.write(90);

  sendAck("boot");
}

// ---------- Ana döngü ----------
void loop() {
  // 1) Step motor adımlama — mümkün olduğu kadar sık çağrılmalı
  for (int i = 0; i < 4; i++) stepper[i].run();

  // 2) Komut pompası
  pollSerial();

  if (motors_enabled && (millis() - last_cmd_ms > CMD_TIMEOUT_MS)) {
    for (int i = 0; i < 4; i++) stepper[i].stop();
    setMotorsEnabled(false);
  }

  // 3) Sensör + telemetri (periyodik)
  uint32_t now = millis();
  if (now - last_tlm_ms >= TLM_PERIOD_MS) {
    last_tlm_ms = now;

    // Encoderlar
    for (int i = 0; i < 4; i++) {
      uint16_t raw;
      if (as5600Read(ENC_CHANNELS[i], raw)) {
        joint[i].encoder_raw = raw;
        joint[i].encoder_deg = raw * (360.0f / 4096.0f);
      }
    }

    sendTelemetry();
  }
}
