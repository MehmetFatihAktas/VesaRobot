// MotorTest_1x_UART.ino
// Tek TMC2209 + tek NEMA17 UART mod testi
// Önce TMC UART bağlantısını doğrular, sonra motoru döndürür.
//
// Bağlantı (S2209 V4.0 breakout, TMC #1 J1, adres 0b00):
//   VM   -> 15V boost
//   GND  -> yıldız GND (üst + alt)
//   VIO  -> Teensy 3.3V
//   A1,A2,B1,B2 -> motor sargıları
//   MS1  -> GND   (adres biti 0)
//   MS2  -> GND   (adres biti 1)
//   TX   -> Teensy pin 7  (Serial2 RX)
//   RX   -> Teensy pin 8  (Serial2 TX)
//   CLK  -> BOŞ
//   EN   -> Teensy pin 12
//   STEP -> Teensy pin 2
//   DIR  -> Teensy pin 3
//
// Kütüphane: TMCStepper (teemuatlut)

#include <Arduino.h>
#include <TMCStepper.h>

#define TMC_SERIAL Serial2
constexpr float    R_SENSE     = 0.11f;   // S2209 V4.0 tipik
constexpr uint8_t  TMC_ADDRESS = 0b00;    // bu test için J1
constexpr uint16_t MICROSTEPS  = 16;
constexpr uint16_t RMS_CURRENT = 500;     // mA — güvenli başlangıç

constexpr uint8_t PIN_STEP = 2;
constexpr uint8_t PIN_DIR  = 3;
constexpr uint8_t PIN_EN   = 12;
constexpr uint8_t PIN_LED  = 13;

TMC2209Stepper driver(&TMC_SERIAL, R_SENSE, TMC_ADDRESS);

constexpr uint32_t STEPS_PER_DIR  = 3200;  // 1 motor turu @ 1/16
constexpr uint32_t STEP_PERIOD_US = 400;   // ~2500 step/s

void pulseStep() {
  digitalWrite(PIN_STEP, HIGH);
  delayMicroseconds(3);
  digitalWrite(PIN_STEP, LOW);
  delayMicroseconds(STEP_PERIOD_US - 3);
}

void setup() {
  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_EN, OUTPUT);
  pinMode(PIN_LED, OUTPUT);

  digitalWrite(PIN_EN, HIGH);      // motor kapalı
  digitalWrite(PIN_DIR, LOW);
  digitalWrite(PIN_STEP, LOW);

  Serial.begin(115200);
  while (!Serial && millis() < 2000) {}
  Serial.println("\n=== MotorTest_1x_UART ===");

  TMC_SERIAL.begin(115200);
  delay(200);

  // UART bağlantı testi — sürücü cevap veriyor mu?
  Serial.print("TMC UART testi... ");
  uint8_t ver = driver.version();
  if (ver == 0 || ver == 0xFF) {
    Serial.print("BASARISIZ (okunan version=0x");
    Serial.print(ver, HEX);
    Serial.println(")");
    Serial.println("Kontrol: TX/RX pinleri, VIO, MS1/MS2 adresi, baud");
    while (1) {
      digitalWrite(PIN_LED, !digitalRead(PIN_LED));
      delay(200);
    }
  }
  Serial.print("OK, TMC version=0x");
  Serial.println(ver, HEX);

  // Konfigürasyon
  driver.begin();
  driver.toff(4);
  driver.rms_current(RMS_CURRENT);
  driver.microsteps(MICROSTEPS);
  driver.pwm_autoscale(true);
  driver.en_spreadCycle(false);         // StealthChop (sessiz)

  Serial.print("rms_current  = "); Serial.println(driver.rms_current());
  Serial.print("microsteps   = "); Serial.println(driver.microsteps());

  Serial.println("5 saniye sonra motor...");
  delay(5000);
  digitalWrite(PIN_EN, LOW);
  Serial.println("ENABLED.");
}

void loop() {
  digitalWrite(PIN_LED, HIGH);
  digitalWrite(PIN_DIR, LOW);
  Serial.println("CW 1 tur");
  for (uint32_t i = 0; i < STEPS_PER_DIR; i++) pulseStep();
  delay(500);

  digitalWrite(PIN_LED, LOW);
  digitalWrite(PIN_DIR, HIGH);
  Serial.println("CCW 1 tur");
  for (uint32_t i = 0; i < STEPS_PER_DIR; i++) pulseStep();
  delay(500);
}
