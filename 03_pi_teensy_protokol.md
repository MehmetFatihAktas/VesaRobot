# RobotKOL — Pi ↔ Teensy Haberleşme Protokolü

## Fiziksel Katman

- **Ana bağlantı:** USB (Pi 5 USB-A ↔ Teensy USB-Micro)
- Teensy'de Linux tarafında `/dev/ttyACM0` olarak görünür
- Baud: önemsiz (Teensy USB yerel hızda)
- Kodlama: UTF-8, satır sonu = `\n`

## Mantıksal Katman

- **Satır bazlı JSON.** Her mesaj tek satır + `\n`.
- Pi → Teensy: **komut**
- Teensy → Pi: **ack** (her komuta) + **telemetri** (periyodik, 20 Hz)

## Pi → Teensy Komutları

### `move` — eksen pozisyon komutu (mutlak, step cinsinden)

```json
{"cmd":"move","j":[1200,-800,400,0],"v":800,"a":1600}
```

| Alan | Tip | Açıklama |
|------|-----|----------|
| `j`  | int[4] | Hedef microstep (mutlak) |
| `v`  | float | Maks hız (microstep/s), opsiyonel |
| `a`  | float | İvme (microstep/s²), opsiyonel |

### `move_deg` — eklem derecesi cinsinden (önerilen)

Gearbox 28.4:1 bilindiği için Teensy step dönüşümünü kendi yapar. `STEPS_PER_DEG = 252.44`.

```json
{"cmd":"move_deg","j":[45.0,-20.0,60.0,0.0],"v":30.0,"a":60.0}
```

| Alan | Tip | Açıklama |
|------|-----|----------|
| `j`  | float[4] | Eklem açıları (°, mutlak) |
| `v`  | float | Maks eklem hızı (°/s), opsiyonel — 0 ise default |
| `a`  | float | Eklem ivmesi (°/s²), opsiyonel |

### `servo` — servo açı

```json
{"cmd":"servo","s":[90,30]}
```

`s[0]` = gripper (0–180°), `s[1]` = bilek.

### `en` — motor enable

```json
{"cmd":"en","on":1}
```

`on=1` motorları tutar, `on=0` serbest bırakır (aktif-düşük EN).

### `stop` — kontrollü durdur

```json
{"cmd":"stop"}
```

Tüm steppers için `stop()` — mevcut ivmeyle yavaşlayıp durur.

### `home` — referans arama (iskelet)

```json
{"cmd":"home"}
```

Şimdilik sadece `currentPosition = 0`; ileride endstop sekansı eklenecek.

### `ping`

```json
{"cmd":"ping"}
```

Yanıt: `{"ack":true,"msg":"pong"}`.

### `scan_i2c` — PCA + encoder varlık taraması

```json
{"cmd":"scan_i2c"}
```

Yanıt örneği:

```json
{"ack":true,"msg":"scan_i2c","pca":true,"channels":[1,2,4,6],"enc":[true,true,true,true]}
```

- `pca=true` ise `0x70` görüldü
- `enc[i]=true` ise ilgili PCA kanalında `0x36` cevap verdi

### `diag` — encoder teşhisi

```json
{"cmd":"diag"}
```

Yanıt örneği:

```json
{
  "ack": true,
  "msg": "diag",
  "t": 4242,
  "en": false,
  "cmd_age_ms": 12,
  "channels": [1,2,4,6],
  "enc_ok": [true,true,true,true],
  "enc_raw": [1024,2030,55,4001],
  "enc_deg": [90.0,178.3,4.8,351.7],
  "enc_agc": [122,118,130,126],
  "enc_mag": [1650,1710,1622,1698],
  "status_md": [true,true,true,true],
  "status_ml": [false,false,false,false],
  "status_mh": [false,false,false,false]
}
```

- `status_md` = mıknatıs algılandı
- `status_ml` = alan zayıf
- `status_mh` = alan güçlü
- `cmd_age_ms` = son geçerli komuttan beri geçen süre

## Teensy → Pi Mesajları

### Ack (her komuttan sonra)

```json
{"ack":true,"msg":"move"}
```

Hata durumunda `ack:false`, `msg` = hata etiketi (`parse_err`, `unknown`, …).

### Telemetri (20 Hz, otomatik yayın)

```json
{
  "t": 128345,
  "enc_deg": [12.3, 45.7, 178.2, 5.0],
  "pos_steps": [11360, -5048, 15146, 0],
  "joint_deg": [45.0, -20.0, 60.0, 0.0],
  "en": true
}
```

| Alan | Açıklama |
|------|----------|
| `t` | Teensy `millis()` |
| `enc_deg` | AS5600 mutlak açı ölçümü (°) — gerçek mekanik |
| `pos_steps` | Stepper komutlu microstep pozisyonu |
| `joint_deg` | Stepper pozisyonu derece cinsinden (gearbox hesabıyla) |
| `en` | Motor enable durumu |

**Not:** `tof_mm` artık Teensy telemetrisinde YOK. VL53L1X Pi'ye direkt bağlı, Pi kendi ROS2 node'unda okur.

**Kapalı çevrim için:** `joint_deg` komutu ne verdiyse, `enc_deg` gerçekte nereye gittiğini söyler. Fark > eşik ise kayıp var demek.

## Pi Tarafı Referans (Python)

```python
import json, serial, threading, time

ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.1)

def reader():
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "ack" in msg:
            print("ACK:", msg)
        elif "enc_deg" in msg:
            # telemetri — ring buffer / state'e yaz
            pass

threading.Thread(target=reader, daemon=True).start()

def send(cmd: dict):
    ser.write((json.dumps(cmd) + "\n").encode())

send({"cmd": "en", "on": 1})
time.sleep(0.1)
send({"cmd": "move", "j": [1600, -800, 0, 0], "v": 800, "a": 1600})
```

## Tasarım Notları

- **Binary protokole geçiş:** 20 Hz telemetri + JSON ~5–10 KB/s, USB için sorun değil. Yük artarsa MessagePack / CBOR / custom binary düşünülür.
- **Watchdog:** Pi, 500 ms içinde ack almazsa yeniden bağlan. Teensy, `500 ms` komut alamazsa `stop()` çağırır ve `enable=0` yapar.
- **Acil durdurma:** Pi tarafında bir flag değişince `stop` + `en:0` arka arkaya gönderilir. Donanımsal E-STOP için Teensy'ye ayrı bir dijital giriş de eklenebilir (pin 20 önerildi).
- **Pozisyon birimi:** Şimdilik step. Üst katman (Pi) step ↔ derece dönüşümünü yapar; kalibrasyon Pi'de JSON'a yazılır. Teensy joint kinematik bilmez.

## Manuel Kontrol Araçları

Repo içinde ROS'suz ilk bring-up için şu araçlar var:

- `pi/manual_cli.py` — terminalden `ping`, `scan_i2c`, `diag`, `move_deg`, `servo`
- `pi/manual_xbox_bridge.py` — Bluetooth Xbox controller → USB serial Teensy köprüsü

Kurulum:

```bash
python3 -m pip install -r pi/requirements-manual.txt
```

İlk doğrulama:

```bash
python3 pi/manual_cli.py --port /dev/ttyACM0
```
