# RobotKOL — Kondansatör (Decoupling / Bypass) Rehberi

## Temel Prensip

Her kondansatörün bir işi var. Tek başlarına yetmezler, **paralel kombinasyon** gerekir:

| Tip | Boyut | Rol |
|-----|-------|-----|
| **Elektrolitik** (veya tantal) | 10 µF – 1000 µF | Düşük frekans gürültüsü, akım darbesi rezervi |
| **Seramik MLCC / disk** ("mercimek") | 100 nF – 10 µF | Yüksek frekans gürültüsü (MHz), anlık besleme |

Kural: **her IC'nin VCC pininin dibinde (≤5 mm) bir 100 nF seramik**. Bu pazarlıksız. Elektrolitik ise regülatör çıkışında + yerel büyük yüklerin yakınında olur.

## Modül Modül — Ne, Nerede, Kaç Tane

### 1) 150W Boost (×4) — TMC2209 besleme

Modül çıkışında zaten büyük elektrolitik var, ama TMC2209'a giden hat ayrı bir noktaya ekstra kondansatör ister.

**Boost girişine (batarya tarafı):**
- Sigortanın hemen arkasına: 470 µF / 25V elektrolitik + 100 nF seramik

**Boost çıkışı → TMC VM pini dibine (her TMC için):**
- **100 µF / 25V low-ESR elektrolitik + 100 nF seramik**, TMC pinine ≤10 mm
- Bu ikisi olmadan TMC StealthChop kaçırır, adım atlar

**TMC VIO (3.3V lojik pini):**
- 10 µF seramik + 100 nF seramik, VIO pinine ≤5 mm

### 2) XL4016 (Pi buck) — 5.1V / Pi 5

Pi 5 ani akım çeker (USB takılması, CPU boost). Buck çıkışına büyük tampon lazım.

**XL4016 girişi:** 470 µF / 25V + 100 nF (modülde büyük ihtimalle var — doğrula)

**XL4016 çıkışı → Pi USB-C konnektörü arasında:**
- **1000 µF / 10V low-ESR + 10 µF seramik + 100 nF seramik**
- Kablo uzunsa (>15 cm), Pi tarafına yakın ikinci bir 470 µF daha koy

### 3) LM2596 (servo buck ×2) — her servo için ayrı

Servolar hareket başlangıcında pik çeker. LM2596'nın iç kondansatörü yetmez.

**LM2596 girişi:** 100 µF / 25V + 100 nF

**LM2596 çıkışı → servo güç konnektörü arasında:**
- **1000 µF / 10V low-ESR elektrolitik + 100 nF seramik**
- Buna rağmen reset atarsa çıkışa **2200 µF**'e çık

**Servoya en yakın yerde (servo konnektöründen 5 cm içinde):**
- 220 µF / 10V elektrolitik (servo kablosu uzunsa zorunlu)

### 4) XL4015 (encoder 5V kademesi ×4) — 11V → 5V

Her encoder için ayrı bir XL4015 olduğundan yükleri hafif (~30 mA). Problem çıkmaz ama yine de:

**XL4015 girişi:** 100 µF / 25V + 100 nF
**XL4015 çıkışı:** 47 µF / 16V + 100 nF

### 5) AMS1117 (3.3V LDO ×4) — 5V → 3.3V

AMS1117 datasheet'i özellikle istiyor:

**AMS1117 girişi:** 10 µF seramik veya tantal + 100 nF seramik
**AMS1117 çıkışı:** 22 µF seramik veya tantal + 100 nF seramik

**Not:** AMS1117 osilasyon yapabilen bir LDO, bu kondansatörler pazarlıksız.

### 6) PCA9548A (I2C mux)

**VCC dibine:** 10 µF seramik + 100 nF seramik

### 7) AS5600 (×4, her biri)

**VCC dibine:** 1 µF seramik + 100 nF seramik, sensör pinine ≤5 mm

### 8) VL53L1X (ToF)

Datasheet'e göre:
**VIN dibine:** 4.7 µF seramik + 100 nF seramik
- Modül breakout'ta zaten olabilir — ölç, yoksa ekle

### 9) Teensy 4.0 — Teensy kartında zaten var

Ekstra eklemeye gerek yok. Ama **USB-Micro konnektörden geliyorsan** Pi tarafında 100 µF + 100 nF kablo gürültüsüne karşı mantıklı.

## Tek Bakışta Alışveriş Listesi

Minimum olmazsa olmaz:

| Değer / Tip | Adet | Nerede |
|-------------|------|--------|
| 1000 µF / 16V low-ESR elektrolitik | 4 | Pi çıkış + 2 servo çıkış + 1 yedek |
| 470 µF / 25V elektrolitik | 6 | boost girişleri + Pi girişi + yedek |
| 220 µF / 10V elektrolitik | 3 | servo yanına yerel + yedek |
| 100 µF / 25V low-ESR elektrolitik | 10 | TMC VM dipleri ×4 + buck girişleri + yedek |
| 47 µF / 16V | 6 | XL4015 çıkışları ×4 + yedek |
| 22 µF seramik veya tantal | 6 | AMS1117 çıkışları ×4 + yedek |
| 10 µF seramik | 20 | bolca her yerde (AMS girişi, PCA, Teensy çevresi vs.) |
| 4.7 µF seramik | 4 | ToF + yedek |
| 1 µF seramik | 10 | AS5600 VCC ×4 + yedek |
| **100 nF seramik ("mercimek")** | **50+** | **her IC'nin VCC'sinde, bol bol** |

## Montaj Kuralları

1. **Mesafe minimum.** 100 nF seramikler IC pinine 5 mm'den uzaksa etkisizdir. PCB'de kısa bacak, havai kabloda doğrudan pinin altına.

2. **GND ayağı kısa.** Kondansatörün GND bacağı yıldıza giden hatta **doğrudan** inmeli, başka bir kablo zincirine karışmamalı.

3. **Paralel + yakın.** "100 µF elektrolitik + 100 nF seramik" ikilisini aynı noktaya **yan yana** koy. Arada 5 cm varsa yüksek frekans tarafı işe yaramaz.

4. **Polarite!** Elektrolitik kondansatörlerin `−` bandı GND'ye. Ters takarsan patlar.

5. **Gerilim 2×.** 15V raya takacağın elektrolitik **min 25V**, 5V raya takacağın **min 10V**, 3.3V raya takacağın **min 10V**. Düşük gerilim anma = erken ölüm.

6. **Low-ESR tercihi.** Servo ve TMC çıkışlarında normal elektrolitik yerine **"low-ESR"** yazan tipler (genelde kırmızı/mor kaplama, "105°C" etiketli) kullan. Servo reset atmalarının %80'i ucuz yüksek ESR kondansatörden gelir.

## Hata Belirtisi → Çözüm

| Belirti | Muhtemel sebep | Ekle |
|---------|----------------|------|
| Servo hareket anında Pi reset | servo çıkış tampon küçük | LM2596 çıkışına 1000 µF low-ESR |
| TMC rastgele adım atlama | VM'de gerilim dalgalanması | TMC VM dibine 100 µF + 100 nF |
| I2C zaman zaman hang | sensör hattında gürültü | PCA ve her AS5600 VCC'ye 100 nF |
| Teensy spontane reset | USB hat üstünde ripple | Pi USB çıkışına 100 µF + 100 nF |
| Boost çıkışı osilasyon | çıkış yüksüz + kondansatör az | çıkışa 220 µF yerel ekle |
| AMS1117 çıkışı osilasyon | çıkış kondansatörü yok/yanlış | 22 µF düşük ESR seramik/tantal |

## Sende Mevcut Olan (2026-04-19)

- 4× TMC2209 üstünde **100 µF / 25V elektrolitik** ✓ (VM pini için doğru değer, doğru gerilim)
- **Seramik (mercimek) HİÇ YOK** ← kritik eksik
- Buck/boost çıkışlarında ek kondansatör yok

## KESİN ALIŞVERİŞ LİSTESİ (Sende olanlar çıkarıldı, 3 katmanlı)

### 🔴 KIRMIZI — Omurga, mutlaka al

| Kalem | Adet | Nerede |
|-------|------|--------|
| **100 nF seramik MLCC (50V) — "104" kodlu** | **50–100** | Her IC pinine, 4 TMC VM yanına, her regülatör giriş/çıkışına, her sensöre. Sistemin kararlılığının %50'si bunda. |
| **1000 µF / 25V low-ESR elektrolitik** | 4 | Pi çıkışı (1) + LM2596 servo çıkışları (2) + 1 yedek. 25V şart — servo hattında spike olur, 16V sınırda kalır. |
| **470 µF / 25V elektrolitik** | 4–6 | 4 boost girişi + opsiyonel Pi buck girişi + yedek |
| **10 µF seramik MLCC (≥16V anma)** | 10 | AMS1117 giriş+çıkışları (×4 × 2) + yedek. **DC bias** nedeniyle düşük anma voltajlı MLCC değer kaybeder — 5V hatta 16V, 15V hatta 25V anma al. |

### 🟡 SARI — İyi olur, ikinci alımda tamamla

| Kalem | Adet | Nerede |
|-------|------|--------|
| **47 µF / 16V elektrolitik** | 4–6 | XL4015 çıkışları (encoder hattı, yardımcı destek) |
| **1 µF seramik** | 8 | Her AS5600 VCC yanında |
| **220 µF / 10V elektrolitik** | 2–3 | Servo kablosu uzunsa konnektör yanına |

### 🟢 YEŞİL — Opsiyonel

| Kalem | Adet | Neden opsiyonel |
|-------|------|-----------------|
| **22 µF tantal** | 0–4 | AMS1117'de 10 µF + 100 nF zaten yeter |
| **4.7 µF seramik** | 0–4 | ToF modülü datasheet ister ama breakout'ta genelde var |

**Not:** 100 µF / 25V elektrolitik listeden çıkarıldı — sende 4 tane var, buck girişleri için de aynı değerlerle idare eder. Low-ESR şart değil.

### 🟢 YARDIMCI — titizlik için

| Kalem | Adet | Nerede |
|-------|------|--------|
| **220 µF / 10V elektrolitik** | 3 adet | Servo konnektörü yanına (kablo uzunsa) |
| **4.7 µF / 10V seramik** | 4 adet | VL53L1X ToF VIN (datasheet ister) + yedek |
| **1 µF / 10V seramik** | 8 adet | Her AS5600 VCC (×4) + yedek |

### Toplam Tahmini Maliyet

- 100 nF seramik ×100: ~20 TL
- Elektrolitikler (hepsi): ~60 TL
- Tantal 22 µF ×6: ~30 TL (tantal pahalı, seramik 22 µF de olur ~15 TL)
- Toplam: **≈110–130 TL**

Shopee/Robotistan/DirenÇarşısı gibi yerlerde "100 nF 50V seramik 100 adet paket" zaten satılıyor.

## Öncelik Sırası — Önce Neyi Takmalı

Bir kerede takamayacaksan, bu sırayla:

1. **100 nF seramik (104) her IC pinine** — en ucuz, en etkili müdahale. Özellikle 4 TMC'nin yanına hemen ekle.
2. **LM2596 servo çıkışlarına 1000 µF low-ESR + 100 nF** — servo reset atmalarını keser.
3. **XL4016 Pi çıkışına 1000 µF + 100 nF** — Pi undervolt uyarılarını keser.
4. **4 Boost girişine 470 µF / 25V + 100 nF** — 4 motor aynı anda hızlanırken stabilite.
5. **AMS1117 giriş/çıkışlarına 10 µF + 100 nF** — sensör hattı temiz olur.
6. **PCA9548A + her AS5600 VCC yanına 10 µF + 100 nF** — I2C kararlılığı.
7. **XL4015 çıkışlarına 47 µF + 100 nF** — encoder hattının 5V kademesi (hafif yük, yeterli).

## Pratik Uyarı — "104" Seramik Kodu

Seramik kondansatör alırken üstlerinde 3 rakamlı kod olur:

| Kod | Değer |
|-----|-------|
| 101 | 100 pF |
| 102 | 1 nF |
| 103 | 10 nF |
| **104** | **100 nF** ← bizim aradığımız |
| 105 | 1 µF |
| 106 | 10 µF |

Mantık: "ilk iki rakam × 10^üçüncü rakam, pF cinsinden". 104 = 10 × 10⁴ pF = 100 000 pF = 100 nF.
