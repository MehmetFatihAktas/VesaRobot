# RobotKOL — Kademeli Bring-up Checklist

> Her adımı **tamamlandı** işaretlemeden bir sonrakine geçme. Sorun çıkarsa güç kesilip tek değişken geri alınır.

## Faz 0 — Tezgâh Hazırlığı

- [ ] Multimetre (V, A, süreklilik) hazır
- [ ] Ayarlı laboratuvar güç kaynağı varsa onu kullan, bataryayı sona bırak
- [ ] Sigorta yuvaları, ATC sigortalar seti (1A, 4A, 6A, 10A) mevcut
- [ ] Isı tabancası / temassız termometre
- [ ] USB izolatör (opsiyonel ama Pi↔Teensy debugging'de çok yararlı)
- [ ] Oturma düzeni: batarya en uzakta, switch/sigorta yakında, her şey erişilebilir

## Faz 1 — Raspberry Pi 5 Hattını Tek Başına Çalıştır

- [ ] Pi buck çıkışını **yükten ayrı** 5.10 ± 0.05 V'a ayarla, trimpot kilitle
- [ ] Yükü bağlamadan önce multimetreyle çıkış kontrolü
- [ ] Pi'yi bağla, SD'de temiz Raspberry Pi OS, HDMI ile boot'u doğrula
- [ ] `vcgencmd get_throttled` → `0x0` olmalı (undervolt yok)
- [ ] 30 dk idle + stress test (`stress-ng --cpu 4`) — buck ısısı, gerilim stabilitesi
- [ ] Pi Camera 3 bağla, `libcamera-hello` ile görüntü al

**Geçiş kriteri:** Pi idle + CPU yükü altında `get_throttled=0x0`, buck çıkışı ≥5.0 V.

## Faz 2 — Teensy'yi USB Üzerinden Pi'ye Tanıt

- [ ] Teensy'nin VIN-VUSB köprüsünü **KES** (ayrı güç gelmesin)
- [ ] Teensy'yi Pi USB'sine tak
- [ ] Pi'de `ls /dev/ttyACM*` → `/dev/ttyACM0`
- [ ] `screen /dev/ttyACM0 115200` → boot mesajı geliyor mu (boş iskeletle: `{"ack":true,"msg":"boot"}`)
- [ ] Pi'den `{"cmd":"ping"}\n` gönder, `{"ack":true,"msg":"pong"}` al

**Geçiş kriteri:** İki yönlü JSON akışı çalışıyor.

## Faz 3 — Sensör 3.3V Rayını Kur

- [ ] AMS1117 modülü yükten **ayrı** test et: 11.8V giriş → 3.30 ± 0.05 V çıkış
- [ ] Hiçbir sensör bağlı değilken çıkış gerilimi stabil
- [ ] Kısa devre testi: çıkışı multimetre süreklilik moduyla yerel GND'ye karşı ölç (kısa olmamalı)
- [ ] Raya **sadece PCA9548A** bağla, sensörler hâlâ sökük, tekrar ölç
- [ ] PCA9548A'nın VCC'si ve I2C pull-up'ları yerinde mi (genelde breakout üstünde 10k)

**Geçiş kriteri:** Sensör rayında 3.3V stabil, PCA9548A bağlıyken de bozulmuyor.

## Faz 4 — Tek AS5600 + PCA9548A

- [ ] 1 adet AS5600'ü kanal 1'e bağla (`1/2/4/6` saha kablolamasına göre)
- [ ] Teensy'de basit I2C scan skeci yükle, sadece Wire üzerinde `0x36` görünsün (mux tek kanal açık)
- [ ] Magneti yakınlaştır → ham açı okunuyor
- [ ] Mıknatıs döndürüldüğünde değer 0–4095 arasında düzgün değişiyor

**Geçiş kriteri:** AS5600 kanal 1'den tutarlı açı veriyor.

## Faz 5 — Diğer 3 Encoder + **AS5600 mıknatıs değerlendirmesi**

- [ ] Sırayla kanal 2, 4, 6'ya diğer AS5600'leri ekle — her ekleme sonrası tekrar oku
- [ ] 4 encoder'ı aynı anda okuyan test skeci (`tcaSelect` + read loop) sorunsuz

> **Not:** VL53L1X ToF artık Teensy tarafında değil. Pi I2C'ye doğrudan bağlanacak. Faz 10'da test edilecek.

### ⚠️ Mıknatıs Mount Değerlendirmesi (ertelenmiş karar)

Mıknatıslar çelik NEMA miline direkt yapışık. Objektif test:

- [ ] `{"cmd":"diag"}` gönder → her 4 encoder için `AGC` + `status` + `raw` oku
- [ ] Her eksen için **AGC 64–192** arasında mı? ✓ iyi
- [ ] Her eksen için **Status: MD=1, MH=0, ML=0** mı? ✓ iyi
- [ ] Her ekseni elle 360° yavaş döndür — `raw` değeri **sıçramasız** 0→4095→0 mu?
- [ ] Kötü çıkan encoder varsa: o ekseni sök, mıknatısı plastik tutucuya taşı, yeniden test
- [ ] 4 encoder de geçti: mıknatıs kararı KAPALI ✓

**Geçiş kriteri:** 4 encoder + ToF tek Wire üzerinde aynı döngüde stabil okunuyor; AGC/status değerleri yeşilde.

## Faz 6 — Tek TMC2209 + Tek NEMA17

- [ ] 15V boost çıkışını yüksüz **15.0 ± 0.2 V**'a ayarla
- [ ] Sürücünün VM'ine sigorta üzerinden bağla, motor henüz takılı değil
- [ ] Vref trimpot ile akım limitini motor spec'inin %70'ine ayarla (ör: 1.2 A motorda ~0.85 A)
- [ ] Motor bağla, `en` = LOW, elle döndürmeyi dene — tutmalı (hafif direnç)
- [ ] STEP/DIR ile 100 step/s yavaş çevir, yön DIR ile değişmeli
- [ ] 5 dk çalışma, sürücü ısısı ≤ 70°C
- [ ] UART ile TMC ile konuş: `tmc.microsteps()`, `tmc.rms_current()` geri okunuyor

**Geçiş kriteri:** Tek eksen pürüzsüz hareket, termal problem yok, UART cevabı geliyor.

## Faz 7 — 4 Motor Aynı Anda

- [ ] Sırayla M2, M3, M4 ekle (MS1/MS2 ile adresleri ayarla)
- [ ] 4'ü birden `AccelStepper` ile farklı hedeflere gönder
- [ ] Boost modülü çıkış gerilimi 4 motor hareket ederken > 14 V kalıyor
- [ ] Ortak EN hattı OK (acil stop test)

**Geçiş kriteri:** 4 eksen aynı anda hareket, güç rayı çökme yapmıyor.

## Faz 8 — Servo 1

- [ ] XL4015 çıkışını **yükten ayrı** 5.0 V'a ayarla, trimpot kilitle
- [ ] Servo bağla, `PWMServo` ile 0 → 90 → 180 → 90 tarama
- [ ] Pik akım ölçümü (pens ampermetre) — buck limiti içinde mi
- [ ] Servo hareketi sırasında sensör okumaları bozulmuyor (en önemli kontrol)

## Faz 9 — Servo 2

- [ ] İkinci servoyu da ekle
- [ ] İki servo aynı anda hareket etsin, XL4015 çıkış gerilimi > 4.7 V
- [ ] Yine encoder/I2C bozulma kontrolü

## Faz 10 — Tam Sistem + VL53L1X (Pi) + Yazılım

### VL53L1X ToF — Pi tarafı

- [ ] Pi'de `sudo raspi-config` → I2C enable
- [ ] `i2cdetect -y 1` → VL53L1X'in `0x29` adresi görünüyor
- [ ] `adafruit-circuitpython-vl53l1x` kur, tek satır Python ile mesafe oku
- [ ] `tof_node` ROS2 node'u `/robotkol/tof_mm` topic'ine yayın yapıyor
- [ ] Elle mesafe değiştir, değer değişimi canlı izleniyor

### Tam sistem

- [ ] Tüm modüller bağlı, final firmware yüklü
- [ ] Pi tarafında telemetri reader + komut gönderici çalışıyor
- [ ] Basit senaryo: `en=1` → `move_deg [45,0,0,0]` → encoder pozisyona yakınsıyor mu
- [ ] ToF değişikliğine göre Pi'de basit "30 cm altında dur" güvenlik davranışı (`safety_guard` node)
- [ ] 10 dk sürekli hareket + log — hiç reset, I2C hang, telemetri kopması yok

**Geçiş kriteri:** Sistem birleşik durumda en az 10 dk kararlı çalışıyor.

## Genel Sorun Giderme İpuçları

| Belirti | İlk bakılacak yer |
|---------|-------------------|
| Pi reset atıyor | Buck çıkış gerilimi + akım, USB periferik pik çekimi |
| I2C hang | Pull-up değerleri, kablo uzunluğu, mux RESET pini |
| Encoder zıplıyor | GND referansı, sensör rayı gürültüsü, magnet mesafesi |
| Motor kaçırıyor | Akım düşük, ivme yüksek, besleme düşüyor |
| TMC ısınıyor | Vref yüksek, StealthChop kapalı, microstep çok yüksek |
| Servo reset yapıyor | Servo hattı çöküyor — kondansatör ekle, XL4015 yükseltmeyi kontrol et |
| USB bağlantı kopuyor | GND loop, USB kablosu, Teensy VIN-VUSB köprüsü |

## Test Ekipmanı Minimum Listesi

- Dijital multimetre
- Pens ampermetre (DC özellikli tercih)
- 11.8 V tezgâh kaynağı (batarya yerine bring-up'ta)
- Değişken yük direnci veya güçlü rezistörler
- Sigorta seti + yedek
- Termometre / IR tabanca
- Oscilloscop (varsa STEP pulsu, servo PWM gözlemi için altın değerinde)
