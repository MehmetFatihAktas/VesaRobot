# RobotKOL — ROS2 Mimarisi (Raspberry Pi 5 / Linux)

## Genel Yapı

```
[Xbox Kontroller] ──USB──► [joy_node] ──► /joy
                                               │
                                               ▼
                                     [robotkol_teleop]
                                               │
                                               ▼
                                   /robotkol/joint_cmd
                                               │
                                               ▼
                                    [teensy_bridge]  ◄── /dev/ttyACM0 ──► [Teensy firmware]
                                               ▲
                                               │
                                   /robotkol/joint_state
                                               ▲
                                               │
                              (Teensy telemetri JSON — enc_deg, joint_deg, pos_steps)

[Pi Camera 3] ──► [camera_node] ──► /image_raw
                                         │
                                         ▼
                                [color_detector]  (otonom mod için, ileride)

[VL53L1X ToF] ── Pi I2C ──► [tof_node] ──► /robotkol/tof_mm
                                                 │
                                                 ▼
                                       [safety_guard]
                                                 │
                                                 ▼
                                    /robotkol/joint_cmd (dur/yavaşla)

[Tümü]                          ▼
                             [planner_node]
                                    │
                                    ▼
                        /robotkol/joint_cmd (teleop yerine)
```

**ToF ayrımı:** VL53L1X artık Teensy'de değil Pi'de okunuyor (Pi I2C GPIO2/3). Avantaj: Pi tarafında kamera + ToF birlikte işlenebilir (nesnenin pikseli + mesafesi → 3B hedef).

## ROS2 Kurulumu

- Hedef: **ROS2 Humble** (Pi 5 + Ubuntu 22.04/24.04) veya **Jazzy** (24.04)
- Windows'ta ilk geliştirme: Humble Windows binary veya WSL2 ile Ubuntu
- Gerçek deploy: Pi 5 üzerinde native Ubuntu + Humble/Jazzy

```bash
# Pi 5 Ubuntu 22.04
sudo apt install ros-humble-ros-base ros-humble-joy ros-humble-joy-linux \
                 ros-humble-v4l2-camera ros-humble-image-transport
```

## Paket Yapısı

```
~/robotkol_ws/
└── src/
    ├── robotkol_msgs/         # Özel mesaj tipleri
    │   └── msg/
    │       ├── JointCommand.msg
    │       └── JointState.msg
    ├── robotkol_bridge/       # Teensy USB-Serial köprüsü
    │   └── robotkol_bridge/
    │       └── teensy_bridge.py
    ├── robotkol_teleop/       # Xbox kol → eklem komutu
    │   └── robotkol_teleop/
    │       └── xbox_teleop.py
    ├── robotkol_sensors/      # Pi'ye direkt bağlı sensörler
    │   └── robotkol_sensors/
    │       └── tof_node.py    # VL53L1X → /robotkol/tof_mm
    ├── robotkol_vision/       # Kamera + renk tespiti (otonom)
    │   └── robotkol_vision/
    │       └── color_detector.py
    └── robotkol_bringup/      # Launch dosyaları
        └── launch/
            ├── manual.launch.py
            └── autonomous.launch.py
```

### `tof_node` (Pi I2C üzerinden VL53L1X)

```python
# tof_node.py — Pi üzerinde VL53L1X okuyup /robotkol/tof_mm yayını
import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt16
import board, busio
import adafruit_vl53l1x  # pip install adafruit-circuitpython-vl53l1x

class TofNode(Node):
    def __init__(self):
        super().__init__('tof_node')
        i2c = busio.I2C(board.SCL, board.SDA)  # Pi GPIO3=SCL, GPIO2=SDA
        self.tof = adafruit_vl53l1x.VL53L1X(i2c)
        self.tof.distance_mode = 2         # Long (4m)
        self.tof.timing_budget = 100       # ms
        self.tof.start_ranging()
        self.pub = self.create_publisher(UInt16, '/robotkol/tof_mm', 10)
        self.create_timer(0.05, self.tick) # 20 Hz

    def tick(self):
        if self.tof.data_ready:
            mm = int(self.tof.distance * 10) if self.tof.distance else 0
            self.tof.clear_interrupt()
            msg = UInt16(); msg.data = mm
            self.pub.publish(msg)

def main():
    rclpy.init()
    rclpy.spin(TofNode())
```

Pi'de I2C aktif olmalı: `sudo raspi-config` → Interface Options → I2C enable.

## Özel Mesaj Tipleri

**`robotkol_msgs/msg/JointCommand.msg`**
```
int32[4] target_steps     # J1..J4 hedef adım (mutlak)
float32  max_speed        # step/s
float32  max_accel        # step/s^2
uint8[2] servo_deg        # J5 (bilek), J6 (gripper)
bool     enable           # motor enable
```

**`robotkol_msgs/msg/JointState.msg`**
```
float32[4] encoder_deg    # AS5600 okuması (°)
int32[4]   stepper_steps  # Teensy'den pozisyon
uint16     tof_mm         # ToF mesafesi
bool       enabled        # motor enable durumu
uint32     t_ms           # Teensy millis()
```

## `teensy_bridge` (ana köprü node)

Görev: ROS2 topic ↔ USB-Serial JSON dönüşümü.

```python
# teensy_bridge.py (özet)
import rclpy
from rclpy.node import Node
import serial, json, threading
from robotkol_msgs.msg import JointCommand, JointState
from std_msgs.msg import UInt16

class TeensyBridge(Node):
    def __init__(self):
        super().__init__('teensy_bridge')
        self.ser = serial.Serial('/dev/ttyACM0', 115200, timeout=0.1)
        self.sub = self.create_subscription(
            JointCommand, '/robotkol/joint_cmd', self.cb_cmd, 10)
        self.pub_state = self.create_publisher(
            JointState, '/robotkol/joint_state', 10)
        self.pub_tof = self.create_publisher(
            UInt16, '/robotkol/tof_mm', 10)
        threading.Thread(target=self.reader, daemon=True).start()

    def cb_cmd(self, msg: JointCommand):
        # Eksen hareketi
        self.send({
            'cmd': 'move',
            'j': list(msg.target_steps),
            'v': msg.max_speed,
            'a': msg.max_accel,
        })
        # Servo
        self.send({'cmd': 'servo', 's': list(msg.servo_deg)})
        # Enable
        self.send({'cmd': 'en', 'on': 1 if msg.enable else 0})

    def send(self, d):
        self.ser.write((json.dumps(d) + '\n').encode())

    def reader(self):
        while rclpy.ok():
            line = self.ser.readline().decode(errors='ignore').strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if 'enc_deg' in m:
                st = JointState()
                st.encoder_deg = [float(x) for x in m['enc_deg']]
                st.stepper_steps = [int(x) for x in m['pos_steps']]
                st.tof_mm = int(m.get('tof_mm', 0))
                st.enabled = bool(m.get('en', False))
                st.t_ms = int(m.get('t', 0))
                self.pub_state.publish(st)
                tof = UInt16(); tof.data = st.tof_mm
                self.pub_tof.publish(tof)

def main():
    rclpy.init()
    rclpy.spin(TeensyBridge())
```

## `xbox_teleop` (manuel kontrol)

Xbox kolu `joy_node` ile `/joy` topic'ine yayın yapar. Biz onu `JointCommand`'e çeviririz.

**Aksiyon eşlemesi (önerilen):**

| Xbox | Ne yapar |
|------|----------|
| Sol analog X | J1 taban döndür |
| Sol analog Y | J2 omuz yukarı/aşağı |
| Sağ analog Y | J3 dirsek yukarı/aşağı |
| Sağ analog X | J4 ön kol yukarı/aşağı |
| LT / RT | Gripper kapat/aç (J6 servo) |
| LB / RB | Bilek sol/sağ (J5 servo) |
| A (yeşil) | Home pozisyonu |
| B (kırmızı) | **Acil stop** (enable=0) |
| X (mavi) | Motor enable toggle |
| Y (sarı) | Otonom moda geç |
| Start | Otonom moddan çık |

```python
# xbox_teleop.py (özet)
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from robotkol_msgs.msg import JointCommand

class XboxTeleop(Node):
    def __init__(self):
        super().__init__('xbox_teleop')
        self.sub = self.create_subscription(Joy, '/joy', self.cb, 10)
        self.pub = self.create_publisher(JointCommand, '/robotkol/joint_cmd', 10)
        self.pos = [0, 0, 0, 0]             # mutlak step takibi
        self.servo = [90, 90]               # bilek, gripper
        self.enabled = False
        self.STEP_PER_TICK = 40              # deadzone üstü her tick'te eksen başı adım
        self.timer = self.create_timer(0.05, self.tick)  # 20 Hz
        self.last_joy = None

    def cb(self, msg: Joy):
        self.last_joy = msg
        # Butonlar — kenar tetiklemeli (basit)
        if msg.buttons[1]:        # B — acil stop
            self.enabled = False
        elif msg.buttons[2]:      # X — enable toggle (debounce eklenebilir)
            self.enabled = not self.enabled

    def tick(self):
        if self.last_joy is None:
            return
        axes = self.last_joy.axes
        def dz(v, d=0.15):  # deadzone
            return 0.0 if abs(v) < d else v

        self.pos[0] += int(dz(axes[0]) * self.STEP_PER_TICK)
        self.pos[1] += int(dz(axes[1]) * self.STEP_PER_TICK)
        self.pos[2] += int(dz(axes[4]) * self.STEP_PER_TICK)
        self.pos[3] += int(dz(axes[3]) * self.STEP_PER_TICK)

        # Gripper (LT=axes[2], RT=axes[5]; -1 basılmamış, +1 basılı — sürüme göre değişir)
        grip_open  = (1 - axes[5]) / 2  # 0..1
        grip_close = (1 - axes[2]) / 2
        self.servo[1] = int(max(0, min(180, 90 + (grip_open - grip_close) * 90)))

        cmd = JointCommand()
        cmd.target_steps = self.pos
        cmd.max_speed = 1200.0
        cmd.max_accel = 2400.0
        cmd.servo_deg = self.servo
        cmd.enable = self.enabled
        self.pub.publish(cmd)
```

## Launch — Manuel

**`robotkol_bringup/launch/manual.launch.py`**
```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package='joy', executable='joy_node', name='joy'),
        Node(package='robotkol_teleop', executable='xbox_teleop'),
        Node(package='robotkol_bridge', executable='teensy_bridge'),
    ])
```

Çalıştır:
```bash
ros2 launch robotkol_bringup manual.launch.py
```

## Otonom Mod (İleri Aşama)

Şu an fikir aşamasında (renkli top sınıflandırma). İlk etapta iskelet bırak:

```
/image_raw → color_detector → /robotkol/target_xy (piksel)
                                       │
                                       ▼
                          simple_planner (piksel → step dönüşümü)
                                       │
                                       ▼
                          /robotkol/joint_cmd
```

**Öneri:** ilk otonom senaryo **çok basit** olsun — "ToF 30 cm altına gelince gripper kapat". Görü entegrasyonu ondan sonra.

## Windows'ta Test Etme

- ROS2 Humble Windows binary çalışır ama `joy` ve seri port yollar farklı (`COM3` vs `/dev/ttyACM0`)
- `teensy_bridge` içinde port parametresini **ROS param**'a bağla:
  ```python
  self.declare_parameter('port', '/dev/ttyACM0')
  port = self.get_parameter('port').value
  self.ser = serial.Serial(port, 115200)
  ```
- Launch dosyasında Windows için `port:=COM3` override

## Kademeli ROS2 Bring-up

1. **`teensy_bridge` tek başına** — `ros2 topic echo /robotkol/joint_state` ile telemetri gelişi doğrula
2. **`joy_node` tek başına** — `ros2 topic echo /joy` ile Xbox girişleri görünüyor mu
3. **`xbox_teleop` ekle** — `/robotkol/joint_cmd` yayınlanıyor mu
4. **Tümü birlikte** — Xbox kolu ile motor hareketi
5. **Sonra kamera, sonra otonom**

## Güvenlik Notu

`xbox_teleop`'ta **watchdog** ekle:
- Son `/joy` mesajı 500 ms üstü eskiyse `enable=0` gönder
- Kol USB'den çıkarsa motorlar serbest düşsün, kendi yerçekimiyle değil, sürücü enable kapanarak

Kod:
```python
def tick(self):
    if self.last_joy is None:
        return
    age = (self.get_clock().now() - self.last_joy_time).nanoseconds / 1e9
    if age > 0.5:
        self.enabled = False  # watchdog trip
    # ...
```
