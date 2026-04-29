# RobotKOL

Tek bataryalı, çok eksenli robot kol platformu.
Raspberry Pi 5 (üst beyin) + Teensy 4.0 (gerçek zamanlı kontrol).

## Donanım Özeti

- 4× NEMA17 + TMC2209 (UART adresli)
- 2× servo (gripper + bilek)
- 4× AS5600 enkoder (TCA9548A I2C mux üzerinden)
- 1× VL53L1X ToF
- Pi Camera 3

## Prototip Kablolama Notu

- PCA9548A üzerinde fiilen kullanılan encoder kanalları `1, 2, 4, 6`'dır. Aradaki boşluklar lehim rahatlığı için bilerek bırakıldı.
- TMC2209 ortak `EN` hattı Teensy pin `12`'ye gider ve sahadaki kurulumda `1k` pull-up ile `3.3V`'a çekilidir.

## Güç Rayları

- 15V boost → step motor sürücüleri
- 5V XL4015 → servolar
- 5.1V buck → Raspberry Pi 5
- 3.3V AMS1117 → sensörler

## Belge Dizini

| Dosya | İçerik |
|-------|--------|
| [01_sistem_mimarisi.md](01_sistem_mimarisi.md) | Güç ağacı, kontrol akışı, GND stratejisi |
| [02_pin_map.md](02_pin_map.md) | Teensy pin atamaları, TMC/AS5600/ToF bağlantıları |
| [03_pi_teensy_protokol.md](03_pi_teensy_protokol.md) | USB-Serial JSON komut/telemetri protokolü |
| [04_bringup_checklist.md](04_bringup_checklist.md) | Kademeli devreye alma testleri |
| [05_kondansator_rehberi.md](05_kondansator_rehberi.md) | Bypass/decoupling kondansatör rehberi |
| [06_ros2_mimarisi.md](06_ros2_mimarisi.md) | ROS2 node yapısı, Xbox teleop, teensy bridge |
| [07_manual_kontrol.md](07_manual_kontrol.md) | ROS'suz ilk bring-up, seri CLI ve Xbox bridge akışı |
| [firmware/RobotKOL_Teensy/](firmware/RobotKOL_Teensy/RobotKOL_Teensy.ino) | Teensy 4.0 firmware iskeleti |

## Bağımlılıklar (Teensy)

Arduino IDE + Teensyduino. Library Manager'dan:

- `AccelStepper`
- `TMCStepper`
- `PWMServo` (Teensyduino ile gelir)
- `VL53L1X` (Pololu)
- `ArduinoJson`

## Hızlı Başlangıç

1. `04_bringup_checklist.md` Faz 0–2'yi uygula
2. `firmware/RobotKOL_Teensy/RobotKOL_Teensy.ino`'yu Teensy'ye yükle
3. Pi'den `/dev/ttyACM0` üzerinden `{"cmd":"ping"}\n` gönder
4. Sonraki fazlara sırayla geç
