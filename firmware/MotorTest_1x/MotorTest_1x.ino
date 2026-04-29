// MotorTest_1x.ino
// Tek TMC2209 + tek NEMA17 için minimum test skeci
// Amaç: motor dönüyor mu? Yön değişiyor mu? Vref doğru mu?
//
// Bağlantı (S2209 V4.0 breakout):
//   VM   -> 15V boost
//   GND  -> yıldız GND (hem üst hem alt GND)
//   VIO  -> Teensy 3.3V
//   A1,A2,B1,B2 -> motor sargıları (multimetreyle doğrulanmış)
//   MS1  -> VIO (1/16 mikrostep)
//   MS2  -> VIO
//   EN   -> Teensy pin 12 (aktif LOW; GND'ye de bağlayabilirsin test için)
//   STEP -> Teensy pin 2
//   DIR  -> Teensy pin 3
//   TX, RX, CLK -> BOŞ
//
// Güvenlik: önce Vref trimpotunu MİNİMUMA çek, yüksüz test et, akımı kademeli artır.

constexpr uint8_t PIN_STEP = 2;
constexpr uint8_t PIN_DIR  = 3;
constexpr uint8_t PIN_EN   = 12;
constexpr uint8_t PIN_LED  = 13;   // onboard durum göstergesi

// --- Hareket parametreleri ---
// 1/16 mikrostep → 3200 microstep / motor turu
// Gearbox 28.4:1 → 3200 * 28.4 = 90880 microstep / eklem turu
// Test için tek motor turu: 3200 microstep
constexpr uint32_t STEPS_PER_DIR = 3200;   // 1 motor turu
constexpr uint32_t STEP_PERIOD_US = 400;   // step periyodu (µs), düşük = hızlı
                                            // 400µs → 2500 step/s → motor ~47 RPM
                                            // yüksüz güvenli, yüklüde biraz yavaşlat

void pulseStep() {
  digitalWrite(PIN_STEP, HIGH);
  delayMicroseconds(3);                    // TMC2209 min HIGH süre: 100ns, rahat
  digitalWrite(PIN_STEP, LOW);
  delayMicroseconds(STEP_PERIOD_US - 3);
}

void setup() {
  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_EN, OUTPUT);
  pinMode(PIN_LED, OUTPUT);

  digitalWrite(PIN_EN, HIGH);              // motor kapalı (güvenli boot)
  digitalWrite(PIN_DIR, LOW);
  digitalWrite(PIN_STEP, LOW);

  Serial.begin(115200);
  while (!Serial && millis() < 2000) {}
  Serial.println("MotorTest_1x boot");
  Serial.println("5 saniye sonra motor calisacak...");
  delay(5000);

  digitalWrite(PIN_EN, LOW);               // motor enable (aktif LOW)
  Serial.println("Motor enabled.");
}

void loop() {
  // İleri yön — 1 motor turu
  digitalWrite(PIN_LED, HIGH);
  digitalWrite(PIN_DIR, LOW);
  Serial.println("CW 1 tur");
  for (uint32_t i = 0; i < STEPS_PER_DIR; i++) {
    pulseStep();
  }

  delay(500);

  // Geri yön — 1 motor turu
  digitalWrite(PIN_LED, LOW);
  digitalWrite(PIN_DIR, HIGH);
  Serial.println("CCW 1 tur");
  for (uint32_t i = 0; i < STEPS_PER_DIR; i++) {
    pulseStep();
  }

  delay(500);

  // İstersen burada dur:
  // digitalWrite(PIN_EN, HIGH); while(1) {}
}
