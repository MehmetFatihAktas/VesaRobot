# RobotKOL — Pin Haritası (Teensy 4.0)

## Teensy 4.0 Pin Atamaları

### Step Motor Sürücüleri (TMC2209 ×4)

| İşlev | Teensy Pin | TMC2209 Pin | Notlar |
|-------|-----------|-------------|--------|
| M1 STEP | 2 | STEP | PWM capable |
| M1 DIR | 3 | DIR | |
| M2 STEP | 4 | STEP | |
| M2 DIR | 5 | DIR | |
| M3 STEP | 6 | STEP | |
| M3 DIR | 9 | DIR | (7,8 UART için ayrıldı) |
| M4 STEP | 10 | STEP | |
| M4 DIR | 11 | DIR | |
| EN (ortak) | 12 | EN | Aktif-düşük, 1k pull-up → VIO |
| TMC UART TX | 8 (Serial2) | PDN_UART | 1k seri direnç önerilir |
| TMC UART RX | 7 (Serial2) | PDN_UART | Tek hat paylaşımı + MS1/MS2 adresleme |

**TMC2209 UART adresleme:** Her sürücüde MS1/MS2 pinlerini farklı (00, 01, 10, 11) bağlayarak 4 sürücü tek UART hattında ayrı ayrı konuşulur.

### Servolar

| İşlev | Teensy Pin | Notlar |
|-------|-----------|--------|
| Servo 1 (gripper) | 14 | PWM, kart kenarinda daha rahat kablolama |
| Servo 2 (bilek) | 15 | PWM, kart kenarinda daha rahat kablolama |

Sinyal GND = Teensy GND. Servo güç GND = ortak yıldız GND.

### I2C — Encoderlar (Teensy tarafı)

| İşlev | Teensy Pin | Hedef |
|-------|-----------|-------|
| SDA (Wire) | 18 | PCA9548A SDA |
| SCL (Wire) | 19 | PCA9548A SCL |

**PCA9548A kanal dağılımı:**

| Kanal | Cihaz | Adres |
|-------|-------|-------|
| 0 | — (boş) | — |
| 1 | AS5600 #1 (J1 — taban) | 0x36 |
| 2 | AS5600 #2 (J2 — omuz) | 0x36 |
| 3 | — (boş) | — |
| 4 | AS5600 #3 (J3 — dirsek) | 0x36 |
| 5 | — (boş) | — |
| 6 | AS5600 #4 (J4 — bilek) | 0x36 |
| 7 | — (yedek) | — |

**Saha notu:** Kanallar `1, 2, 4, 6` bilerek seçildi; PCA breakout üzerinde araya boşluk bırakılarak lehimleme kolaylaştırıldı.

**PCA9548A adres/reset bağlantısı:** `A0`, `A1`, `A2` → `GND` (adres `0x70`), `RESET` → `VCC/3.3V`. `RESET` için ayrı Teensy pini kullanılmıyor.

**PCA9548A beslemesi:** AS5600 #1'in AMS1117 çıkışından **paralel** alınır (ayrı sensör rayı kurulmadı). Encoder 1 hattı sigortası bu yüzden T630mA (diğer 3 hattın T500mA yerine).

### I2C — ToF (Pi tarafı)

VL53L1X artık Teensy/PCA'da DEĞİL, **direkt Raspberry Pi'nin I2C bus'ına** bağlı.

| İşlev | Pi Pin | Hedef |
|-------|--------|-------|
| 3.3V | Pin 1 (3V3) | VL53L1X VIN |
| GND | Pin 6 | VL53L1X GND |
| SDA | Pin 3 (GPIO2) | VL53L1X SDA |
| SCL | Pin 5 (GPIO3) | VL53L1X SCL |

Not: Pi I2C bus'ta onboard 1.8kΩ pull-up var, ek direnç gerekmez. ToF modülünün kendi pull-up'ları da genelde breakout üstünde.

### Raspberry Pi ↔ Teensy

| İşlev | Pi | Teensy |
|-------|----|----|
| USB-Serial | USB-A | USB-Micro |
| (yedek) UART RX | GPIO14 (TXD) | Pin 0 (RX1) |
| (yedek) UART TX | GPIO15 (RXD) | Pin 1 (TX1) |
| GND | GND | GND |

> Ana bağlantı USB. UART yalnız acil/telemetri yedeği olarak tutulabilir.

### Yedek / İsteğe Bağlı Pinler

| Pin | Potansiyel Kullanım |
|-----|---------------------|
| 13 | Onboard LED (status) |
| 14,15 | Serial3 (debug veya Pi yedek UART) |
| 16,17 | Wire1 SCL/SDA (yedek I2C) |
| 20 | Limit switch / home |
| 24,25 | Wire2 (yedek) |

## TMC2209 Sürücü Tarafı

| TMC2209 Pin | Bağlantı |
|-------------|----------|
| VM | 15V raya + 100 µF elektrolitik + 100 nF seramik (yerel) |
| GND | Yıldız GND |
| VIO | Teensy 3.3V |
| STEP, DIR, EN | Yukarıdaki Teensy pinleri |
| MS1, MS2 | UART adresi seçimi (aşağıya bak) |
| PDN_UART | Ortak UART hattı (Teensy Serial2 TX üzerinden 1k) |
| SPREAD | Pull-down (StealthChop) |
| DIAG | (isteğe bağlı) Teensy'ye stall algılama |

**UART adres seçimi:**

| Sürücü | MS1 | MS2 | UART Adres |
|--------|-----|-----|-----------|
| M1 | GND | GND | 0b00 |
| M2 | VIO | GND | 0b01 |
| M3 | GND | VIO | 0b10 |
| M4 | VIO | VIO | 0b11 |

## AS5600 Bağlantısı (her biri)

| AS5600 Pin | Bağlantı |
|------------|----------|
| VCC | 3.3V sensör rayı |
| GND | Yıldız GND |
| SDA | PCA9548A SDx |
| SCL | PCA9548A SCx |
| DIR | Aynı encoder kartının GND pinine kısa köprü |
| OUT/PGO | Boşta |

## VL53L1X Bağlantısı (Pi'ye direkt)

| VL53L1X Pin | Bağlantı |
|-------------|----------|
| VIN | Pi Pin 1 (3.3V) |
| GND | Pi Pin 6 (GND) |
| SDA | Pi Pin 3 (GPIO2, SDA1) |
| SCL | Pi Pin 5 (GPIO3, SCL1) |
| XSHUT | Boşta (istenirse Pi GPIO'ya alınabilir) |
| GPIO1 | Boşta |

**Kritik:** Pi 5 ve Teensy GND'leri **ortak** olacak (yıldız GND üzerinden). Aksi halde USB haberleşmesi + sensör okumaları gürültü alır.
