# RobotKOL — Sistem Mimarisi (v2, gerçek modüllere göre)

## Donanım Özeti

**Mekanik:**
- J1 (taban, 360° dönüş): NEMA17 + TMC2209
- J2, J3, J4 (kol ileri/aşağı eksenleri): 3× NEMA17 + TMC2209
- J5 (bilek dönüş): servo
- J6 (gripper): servo

**Batarya:** 3S LiPo, 4000 mAh, 40A deşarj. Nominal 11.1V, dolu 12.6V, deşarj ~9V.

## Güç Ağacı — Gerçek Modüllerle

```
                    [ 3S LiPo — 12.6V / 4000mAh / 40A ]
                                   │
                              [ANA ŞALTER]
                                   │
        ┌────┬────┬────┬────┬───────┬──────┬──────┬───────┬──────┬──────┬──────┐
        │    │    │    │    │       │      │      │       │      │      │
     [T3.15][T3.15][T3.15][T3.15] [T3.15][T3A][T3A] [T630mA][T500][T500][T500]
      Mot1   Mot2   Mot3   Mot4    Pi    Sv1   Sv2   Enc1    Enc2  Enc3  Enc4
        │    │    │    │    │       │      │      │          │      │      │
      BOOST BOOST BOOST BOOST  XL4016  LM  LM    XL4015×4
      150W  150W  150W  150W   8A     2596 2596  (her biri sigortalı)
        │    │    │    │       │      │     │     │ │ │ │
       15V  15V  15V  15V    5.1V   5.5V  5.5V   5V×4
        │    │    │    │       │      │     │     │ │ │ │
       TMC  TMC  TMC  TMC    Pi 5   Svo1  Svo2  AMS1117×4 (her biri)
       J1   J2   J3   J4    +Teensy                │ │ │ │
        │    │    │    │    USB ile              3.3V#1  #2 #3 #4
       NEMA NEMA NEMA NEMA    ▲                    │
       J1   J2   J3   J4      │                    ├── AS5600#1 + ◄ PCA9548A ◄ paralel
                              │                    ├── AS5600#2
                              │                    ├── AS5600#3
                              │                    └── AS5600#4
                              │
                              └── Pi I2C (GPIO2/3) ◄── VL53L1X
                              └── Pi CSI           ◄── Cam Module 3

(Teensy USB'den beslenir — VIN-VUSB köprüsü KESİK)
```

## Neden Her TMC'ye Ayrı Boost?

- **İzolasyon:** bir sürücü arızalanırsa diğerleri etkilenmez
- **Pik akım:** bir boost 6A max; 4 motor aynı anda hızlanırken tek boost'u zorlar
- **Gürültü ayrımı:** her TMC kendi yerel enerji kaynağından beslenir

## Neden Her Encoder'a Ayrı 5V + Ayrı 3.3V?

- **İzolasyon:** bir encoder ölürse diğerlerinin 3.3V hattı bozulmaz
- **İki kademeli düşürme** (12V → 5V buck, sonra 5V → 3.3V LDO): AMS1117'nin ısınmasını azaltır, ripple düşer
- AMS1117 girişi 4.8–10.3V olduğu için 12V direkt veremezdin — zaten bu yüzden 5V ara kademe var

## Kritik Uyarılar

### 1) 150W Boost modülünün kısa devre koruması YOK
- **Girişe sigorta şart** (her boost için 3A ATC yeterli)
- **Çıkışa da sigorta şart** (15V tarafında 2A — motor kilitlenmesi durumunda TMC'yi + boost'u koruyor)
- 4A üstü yükte **fan zorunlu** (4 veya 5 cm 12V fan, boost girişinden beslenebilir)

### 2) XL4016 (Pi hattı) sınırda
- Pi 5 pik 5A çeker, XL4016 sürekli 5A sınırı
- **Alüminyum soğutucu + 30mm fan** zorunlu
- Giriş sigortası 6A, çıkış 5A
- Çıkış gerilimi **yük altında** ölçülüp 5.10 ± 0.05 V'a kilitlenmeli

### 3) XL4015 encoder hattı batarya deşarjında sınırda
- XL4015 min giriş 8V, 3S LiPo deşarj kesimi ~9V
- Batarya 9V'a inince encoder hattı kararsızlaşır
- **Çözüm:** BMS veya yazılımda 10.5V alt limit uyarısı (3.5V/hücre); Pi bu noktada güvenli park komutu verir

### 4) LM2596 servo sınırda
- MG996R/DS3218 pik 2–2.5A; LM2596 max 3A (+ soğutucu)
- **Her servoya ayrı LM2596** (senin planın zaten bu) ✓
- Çıkışta **1000 µF low-ESR + 100 nF** olmadan servo reset atar

## Sigorta Haritası (Final — cam sigorta, T tipi gecikmeli)

| Dal | Sigorta | Yer |
|-----|---------|-----|
| Boost J1 girişi | **T3.15A** | batarya tarafı |
| Boost J2 girişi | **T3.15A** | batarya tarafı |
| Boost J3 girişi | **T3.15A** | batarya tarafı |
| Boost J4 girişi | **T3.15A** | batarya tarafı |
| Pi buck (XL4016) girişi | **T3.15A** | batarya tarafı |
| Servo buck 1 (LM2596) girişi | **T3A** | batarya tarafı |
| Servo buck 2 (LM2596) girişi | **T3A** | batarya tarafı |
| Encoder 1 buck (XL4015) girişi — **+ PCA9548A paylaşımlı** | **T630mA** | batarya tarafı |
| Encoder 2 buck girişi | **T500mA** | batarya tarafı |
| Encoder 3 buck girişi | **T500mA** | batarya tarafı |
| Encoder 4 buck girişi | **T500mA** | batarya tarafı |

**Not:** Encoder 1 hattı yalnızca AS5600 #1'i değil, **PCA9548A'yı da** besleyecek. Bu yüzden diğer encoderlardan ~2 kademe yüksek sigorta (T630mA). PCA atsa diğer 3 encoder da konuşamaz — tek nokta arıza, ama projenin mevcut durumu için kabul edildi.

## GND Stratejisi — Güncellenmiş

Tek yıldız GND (bataryanın − ucu):

```
                [ Batarya − ]  ← YILDIZ NOKTA
                      │
    ┌────┬────┬────┬──┼──┬────┬────┬────┬────┐
    │    │    │    │  │   │    │    │    │    │
  Boost×4      Pi buck   LM2596×2   Enc buck×4
  GND          GND        GND        GND
  (kalın)    (orta)      (orta)    (ince — sensör hattı)
```

**Önemli:** Sinyal GND (Teensy–sürücü STEP/DIR–encoder I2C) ve güç GND (TMC motor akımı dönüşü, servo akımı dönüşü) **ayrı kablolarla** yıldız noktaya gider. Aynı kablodan dizme — bu yapılmazsa encoder zıplar, I2C bozulur.

## Kontrol Akışı (güncel — ToF Pi'ye taşındı)

```
Kamera → Pi 5 (ROS2, Linux) ◄── VL53L1X (Pi I2C GPIO2/3)
              │
              ▼  USB
           Teensy 4.0 (gerçek zamanlı)
              │
     ┌────────┼──────────────┐
     ▼        ▼              ▼
  STEP/DIR   PWM          I2C (Wire)
  TMC2209×4  Servo×2       PCA9548A (kanal 1/2/4/6 kullaniliyor)
  NEMA×4                   └─ AS5600 ×4

Manuel kontrol: Xbox kol → Pi (joy node) → Teensy bridge
Otonom: Kamera + ToF → Pi görü düğümü → Teensy bridge
```

**Mimari ayrım:**
- **Pi (yüksek seviye):** kamera, ToF, görü, planlama
- **Teensy (gerçek zamanlı):** motor, servo, eksen encoderları
- Bridge: USB-Serial JSON

## İş Birimleri Dosyaları

| Dosya | İçerik |
|-------|--------|
| `02_pin_map.md` | Teensy ↔ sürücü/sensör pin atamaları |
| `03_pi_teensy_protokol.md` | USB-Serial JSON protokolü |
| `04_bringup_checklist.md` | Kademeli devreye alma |
| `05_kondansator_rehberi.md` | Bypass/decoupling rehberi |
| `06_ros2_mimarisi.md` | ROS2 node yapısı, Xbox kontrol, bridge |
| `firmware/RobotKOL_Teensy/` | Teensy firmware |
