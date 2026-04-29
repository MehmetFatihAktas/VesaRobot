# RobotKOL — Manuel Kontrol ve Bring-up

Bu fazın amacı otonom tarafı devreye almadan önce şu zinciri doğrulamaktır:

```text
Xbox (Bluetooth) -> Raspberry Pi -> USB serial -> Teensy -> TMC2209 / servo
                                           \-> PCA9548A -> AS5600
```

## Dosyalar

- `pi/manual_cli.py` — seri terminal / komut satırı aracı
- `pi/manual_xbox_bridge.py` — Xbox gamepad bridge
- `pi/manual_xbox_bridge_win.py` — Windows + Xbox + COM bridge
- `pi/manual_profile.example.json` — hız, limit ve gamepad profil örneği
- `pi/manual_profile.windows.example.json` — Windows Xbox profil örneği
- `pi/setup_manual_env.sh` — Python venv + bağımlılık kurulumu
- `pi/setup_manual_env_win.ps1` — Windows venv + bağımlılık kurulumu
- `pi/run_manual_cli.sh` — portu otomatik bulup CLI açar
- `pi/run_manual_xbox.sh` — portu otomatik bulup Xbox bridge başlatır
- `pi/run_manual_cli_win.ps1` — Windows CLI launcher
- `pi/run_manual_xbox_win.ps1` — Windows Xbox launcher
- `03_pi_teensy_protokol.md` — JSON komutları

## 1. Pi Tarafı Kurulum

```bash
cd ~/VesaRobot
chmod +x pi/*.sh
./pi/setup_manual_env.sh
```

Xbox controller Linux'ta `bluetoothctl` ile eşleşmiş olmalı. Teensy USB ile `/dev/ttyACM0` olarak görünmeli.

İzinler:

```bash
sudo usermod -aG dialout,input $USER
newgrp dialout
```

Gerekirse oturumu kapatıp aç.

Kontrol:

```bash
ls /dev/ttyACM*
./pi/run_manual_cli.sh
```

## 2. İlk Seri Test (motor güçleri kapalıyken)

CLI içinde sırayla:

```text
ping
scan
diag
telemetry on
status
```

Beklenen:

- `ping` -> `{"ack":true,"msg":"pong"}`
- `scan` -> `pca=true`, `enc=[true,true,true,true]`
- `diag` -> `channels=[1,2,4,6]`
- `status_md=true`, `status_ml=false`, `status_mh=false` ideal

Bu aşamada servo ve motor güçleri kapalı olabilir; amaç encoder/PCA hattını doğrulamaktır.

## 3. Tek Eksen Manuel Test

Önce sadece tek TMC + tek motor hattını enerjilendir.

CLI:

```text
en 1
move_deg 5 0 0 0 20 40
move_deg 0 0 0 0 20 40
stop
en 0
```

Beklenen:

- Motor yumuşak kalkar/durur
- `joint_deg` komut yönünde değişir
- ilgili `enc_deg` fiziksel hareketi takip eder

Sorun varsa 4 motoru birlikte deneme.

## 4. Servo Testi

Servo güçleri açıkken:

```text
servo 90 90
servo 120 90
servo 60 120
```

Not: protokolde `servo` sırası:

```text
s[0] = gripper
s[1] = bilek
```

## 5. Xbox Bridge

İlk çalıştırmada script `pi/manual_profile.json` dosyasını otomatik üretir. Gerekirse limit ve hızları oradan düzenle.

Çalıştır:

```bash
./pi/run_manual_xbox.sh
```

Varsayılan kontrol eşlemesi:

```text
A           -> basılı tutunca hareket enable (deadman)
B           -> stop + disable
Left X      -> J1
Left Y      -> J2
Right Y     -> J3
Right X     -> J4
LB / RB     -> bilek servo
LT / RT     -> gripper servo
```

## 5B. Windows + Xbox Bridge

Windows tarafında Linux `evdev` sürümü değil, `pygame` tabanlı bridge kullanılır.

Kurulum:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\pi\setup_manual_env_win.ps1
```

CLI:

```powershell
.\pi\run_manual_cli_win.ps1
```

Xbox bridge:

```powershell
.\pi\run_manual_xbox_win.ps1
```

İlk çalıştırmada `pi/manual_profile.windows.json` oluşturulur. Varsayılan eşleme:

```text
A           -> basılı tutunca enable (deadman)
B           -> stop + disable
Start       -> home
Left X      -> J1
Left Y      -> J2
Right Y     -> J3
Right X     -> J4
LB / RB     -> bilek servo
LT / RT     -> gripper servo
```

Not:

- COM port otomatik bulunur (`VID_16C0 PID_0483`)
- Gerekirse manuel ver:

```powershell
.\pi\run_manual_xbox_win.ps1 COM5
```

## 6. Güvenlik Kuralları

- İlk açılışta robot kol mekanik olarak boşlukta olsun
- Motorları ilk kez düşük hızda test et
- `A` bırakılınca bridge `stop` + `en:0` gönderir
- Teensy tarafında `500 ms` komut gelmezse watchdog motorları serbest bırakır
- `home` komutu şu aşamada **fiziksel homing değil**, sadece step sayacını sıfırlar

## 7. Test Sırası

1. `manual_cli.py` ile `ping`
2. `scan` + `diag`
3. tek motor
4. dört motor
5. servo
6. Xbox bridge

Otonom tarafına bundan önce geçme.
