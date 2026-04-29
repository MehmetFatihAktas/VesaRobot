from __future__ import annotations

import argparse
import json
import threading
import time
from pathlib import Path
from typing import Any

from evdev import InputDevice, ecodes, list_devices

from teensy_link import TeensyLink


DEFAULT_PROFILE: dict[str, Any] = {
    "serial_port": "/dev/ttyACM0",
    "baudrate": 115200,
    "controller_name_contains": "Xbox",
    "tick_hz": 20.0,
    "deadzone": 0.18,
    "joint_max_speed_deg_s": [45.0, 30.0, 30.0, 40.0],
    "joint_limits_deg": [[-180.0, 180.0], [-90.0, 90.0], [-110.0, 110.0], [-110.0, 110.0]],
    "servo_step_deg_s": {"wrist": 90.0, "gripper": 120.0},
    "servo_limits_deg": {"wrist": [0.0, 180.0], "gripper": [0.0, 180.0]},
    "command_speed_deg_s": 45.0,
    "command_accel_deg_s2": 90.0,
    "invert_axes": {"j1": False, "j2": True, "j3": True, "j4": False},
    "print_telemetry_hz": 2.0,
}


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def load_profile(path: Path | None) -> dict[str, Any]:
    profile = json.loads(json.dumps(DEFAULT_PROFILE))
    if path is None:
        return profile
    with path.open("r", encoding="utf-8") as fh:
        custom = json.load(fh)
    for key, value in custom.items():
        if isinstance(value, dict) and isinstance(profile.get(key), dict):
            profile[key].update(value)
        else:
            profile[key] = value
    return profile


def find_controller(name_contains: str) -> InputDevice:
    for dev_path in list_devices():
        dev = InputDevice(dev_path)
        if name_contains.lower() in dev.name.lower():
            return dev
    available = [InputDevice(path).name for path in list_devices()]
    raise RuntimeError(f"Controller containing '{name_contains}' bulunamadi. Mevcut: {available}")


class XboxBridge:
    def __init__(self, profile: dict[str, Any], device: InputDevice, link: TeensyLink):
        self.profile = profile
        self.device = device
        self.link = link
        self.axes: dict[int, float] = {}
        self.buttons: dict[int, int] = {}
        self.running = True
        self.controller_alive = True
        self.motion_enabled = False
        self.targets_deg = [0.0, 0.0, 0.0, 0.0]
        self.servos = [90.0, 90.0]  # [gripper, wrist]
        self._last_print = 0.0
        self._last_tick = time.monotonic()
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    def _normalize_abs(self, code: int, value: int) -> float:
        absinfo = self.device.absinfo(code)
        if absinfo is None:
            return 0.0
        minimum, maximum = absinfo.min, absinfo.max
        if maximum == minimum:
            return 0.0
        if code in (ecodes.ABS_Z, ecodes.ABS_RZ):
            return (value - minimum) / float(maximum - minimum)
        center = (maximum + minimum) / 2.0
        span = (maximum - minimum) / 2.0
        return clamp((value - center) / span, -1.0, 1.0)

    def _reader_loop(self) -> None:
        try:
            for event in self.device.read_loop():
                if event.type == ecodes.EV_ABS:
                    self.axes[event.code] = self._normalize_abs(event.code, event.value)
                elif event.type == ecodes.EV_KEY:
                    self.buttons[event.code] = event.value
                    if event.code == ecodes.BTN_EAST and event.value == 1:
                        self._stop_and_disable()
        except OSError:
            self.controller_alive = False
            self.running = False
            self._stop_and_disable()

    def _axis(self, code: int) -> float:
        value = self.axes.get(code, 0.0)
        deadzone = float(self.profile["deadzone"])
        return 0.0 if abs(value) < deadzone else value

    def _button(self, code: int) -> bool:
        return bool(self.buttons.get(code, 0))

    def _stop_and_disable(self) -> None:
        self.link.send({"cmd": "stop"})
        self.link.send({"cmd": "en", "on": 0})
        self.motion_enabled = False

    def _print_state(self) -> None:
        now = time.monotonic()
        if now - self._last_print < 1.0 / float(self.profile["print_telemetry_hz"]):
            return
        self._last_print = now
        tlm = self.link.latest_telemetry
        if tlm is None:
            return
        print(
            json.dumps(
                {
                    "enabled": self.motion_enabled,
                    "target_deg": [round(v, 1) for v in self.targets_deg],
                    "enc_deg": [round(float(v), 1) for v in tlm.get("enc_deg", [])],
                    "joint_deg": [round(float(v), 1) for v in tlm.get("joint_deg", [])],
                    "servo": [round(v, 1) for v in self.servos],
                },
                ensure_ascii=False,
            )
        )

    def run(self) -> None:
        print("Xbox bridge hazir. A basili tut = hareket enable, B = stop/disable")
        while self.running and self.controller_alive:
            now = time.monotonic()
            dt = now - self._last_tick
            self._last_tick = now

            deadman = self._button(ecodes.BTN_SOUTH)
            if deadman and not self.motion_enabled:
                self.link.send({"cmd": "en", "on": 1})
                self.motion_enabled = True
            elif not deadman and self.motion_enabled:
                self._stop_and_disable()

            if self.motion_enabled:
                joint_axes = [
                    self._axis(ecodes.ABS_X),
                    self._axis(ecodes.ABS_Y),
                    self._axis(ecodes.ABS_RY),
                    self._axis(ecodes.ABS_RX),
                ]
                invert = self.profile["invert_axes"]
                signs = [
                    -1.0 if invert["j1"] else 1.0,
                    -1.0 if invert["j2"] else 1.0,
                    -1.0 if invert["j3"] else 1.0,
                    -1.0 if invert["j4"] else 1.0,
                ]

                for idx, axis_value in enumerate(joint_axes):
                    speed = float(self.profile["joint_max_speed_deg_s"][idx])
                    lo, hi = self.profile["joint_limits_deg"][idx]
                    self.targets_deg[idx] += axis_value * signs[idx] * speed * dt
                    self.targets_deg[idx] = clamp(self.targets_deg[idx], float(lo), float(hi))

                wrist_step = float(self.profile["servo_step_deg_s"]["wrist"])
                gripper_step = float(self.profile["servo_step_deg_s"]["gripper"])
                wrist_dir = (1.0 if self._button(ecodes.BTN_TR) else 0.0) - (
                    1.0 if self._button(ecodes.BTN_TL) else 0.0
                )
                grip_dir = self.axes.get(ecodes.ABS_RZ, 0.0) - self.axes.get(ecodes.ABS_Z, 0.0)

                self.servos[1] += wrist_dir * wrist_step * dt
                self.servos[0] += grip_dir * gripper_step * dt

                wrist_lo, wrist_hi = self.profile["servo_limits_deg"]["wrist"]
                grip_lo, grip_hi = self.profile["servo_limits_deg"]["gripper"]
                self.servos[1] = clamp(self.servos[1], float(wrist_lo), float(wrist_hi))
                self.servos[0] = clamp(self.servos[0], float(grip_lo), float(grip_hi))

                self.link.send(
                    {
                        "cmd": "move_deg",
                        "j": [round(v, 3) for v in self.targets_deg],
                        "v": float(self.profile["command_speed_deg_s"]),
                        "a": float(self.profile["command_accel_deg_s2"]),
                    }
                )
                self.link.send({"cmd": "servo", "s": [int(round(v)) for v in self.servos]})

            self._print_state()
            time.sleep(1.0 / float(self.profile["tick_hz"]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RobotKOL Xbox -> Teensy manual bridge")
    parser.add_argument("--port", default=None, help="Teensy serial port override")
    parser.add_argument(
        "--profile",
        type=Path,
        default=None,
        help="JSON profile path (bkz. pi/manual_profile.example.json)",
    )
    parser.add_argument("--device", default=None, help="Controller event device path, ornek /dev/input/event4")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = load_profile(args.profile)
    port = args.port or profile["serial_port"]
    link = TeensyLink(port, int(profile["baudrate"]))

    try:
        print(json.dumps(link.request({"cmd": "ping"}), ensure_ascii=False))
        print(json.dumps(link.request({"cmd": "scan_i2c"}), ensure_ascii=False))
        device = InputDevice(args.device) if args.device else find_controller(profile["controller_name_contains"])
        print(f"Controller: {device.name} ({device.path})")
        XboxBridge(profile, device, link).run()
    finally:
        try:
            link.send({"cmd": "stop"})
            link.send({"cmd": "en", "on": 0})
        except Exception:
            pass
        link.close()


if __name__ == "__main__":
    main()
