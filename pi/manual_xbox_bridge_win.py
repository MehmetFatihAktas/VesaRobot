from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import pygame
from serial.tools import list_ports

from teensy_link import TeensyLink


DEFAULT_PROFILE: dict[str, Any] = {
    "serial_port": "",
    "baudrate": 115200,
    "tick_hz": 20.0,
    "deadzone": 0.18,
    "joint_max_speed_deg_s": [20.0, 15.0, 15.0, 20.0],
    "joint_limits_deg": [[-180.0, 180.0], [-90.0, 90.0], [-110.0, 110.0], [-110.0, 110.0]],
    "servo_step_deg_s": {"wrist": 60.0, "gripper": 90.0},
    "servo_limits_deg": {"wrist": [0.0, 180.0], "gripper": [0.0, 180.0]},
    "command_speed_deg_s": 25.0,
    "command_accel_deg_s2": 50.0,
    "invert_axes": {"j1": False, "j2": True, "j3": True, "j4": False},
    "mapping": {
        "axes": {"j1": 0, "j2": 1, "j4": 3, "j3": 4, "lt": 2, "rt": 5},
        "buttons": {"deadman_a": 0, "stop_b": 1, "wrist_lb": 4, "wrist_rb": 5, "home_start": 7},
    },
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


def normalize_trigger(raw: float) -> float:
    # XInput/DirectInput farki icin her iki araligi da kabul et
    if raw < 0.0:
        return clamp((raw + 1.0) / 2.0, 0.0, 1.0)
    return clamp(raw, 0.0, 1.0)


def autodetect_teensy_port() -> str:
    for port in list_ports.comports():
        if port.vid == 0x16C0 and port.pid == 0x0483:
            return port.device
    for port in list_ports.comports():
        if "USB Serial Device" in (port.description or ""):
            return port.device
    raise RuntimeError("Teensy COM port bulunamadi.")


def select_joystick(index: int = 0) -> pygame.joystick.Joystick:
    pygame.joystick.init()
    count = pygame.joystick.get_count()
    if count == 0:
        raise RuntimeError("Xbox controller bulunamadi.")
    if index >= count:
        raise RuntimeError(f"Istenen joystick index'i yok: {index}, mevcut: {count}")
    js = pygame.joystick.Joystick(index)
    js.init()
    return js


class WindowsXboxBridge:
    def __init__(self, profile: dict[str, Any], joystick: pygame.joystick.Joystick, link: TeensyLink):
        self.profile = profile
        self.js = joystick
        self.link = link
        self.motion_enabled = False
        self.targets_deg = [0.0, 0.0, 0.0, 0.0]
        self.servos = [90.0, 90.0]  # [gripper, wrist]
        self.prev_buttons: dict[int, bool] = {}
        self.last_print = 0.0
        self.last_tick = time.monotonic()

    def _axis(self, idx: int) -> float:
        if idx >= self.js.get_numaxes():
            return 0.0
        value = float(self.js.get_axis(idx))
        dz = float(self.profile["deadzone"])
        return 0.0 if abs(value) < dz else value

    def _button(self, idx: int) -> bool:
        if idx >= self.js.get_numbuttons():
            return False
        return bool(self.js.get_button(idx))

    def _edge(self, idx: int) -> bool:
        current = self._button(idx)
        prev = self.prev_buttons.get(idx, False)
        self.prev_buttons[idx] = current
        return current and not prev

    def _stop_and_disable(self) -> None:
        self.link.send({"cmd": "stop"})
        self.link.send({"cmd": "en", "on": 0})
        self.motion_enabled = False

    def _print_state(self) -> None:
        now = time.monotonic()
        if now - self.last_print < 1.0 / float(self.profile["print_telemetry_hz"]):
            return
        self.last_print = now
        tlm = self.link.latest_telemetry
        if not tlm:
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
        mapping = self.profile["mapping"]
        axes = mapping["axes"]
        buttons = mapping["buttons"]
        invert = self.profile["invert_axes"]

        print(
            "Windows Xbox bridge hazir. "
            "A basili tut = enable, B = stop, Start = home, Ctrl+C = cikis"
        )

        while True:
            pygame.event.pump()

            now = time.monotonic()
            dt = now - self.last_tick
            self.last_tick = now

            if self._edge(int(buttons["stop_b"])):
                self._stop_and_disable()

            if self._edge(int(buttons["home_start"])):
                self.link.send({"cmd": "home"})

            deadman = self._button(int(buttons["deadman_a"]))
            if deadman and not self.motion_enabled:
                self.link.send({"cmd": "en", "on": 1})
                self.motion_enabled = True
            elif not deadman and self.motion_enabled:
                self._stop_and_disable()

            if self.motion_enabled:
                joint_axes = [
                    self._axis(int(axes["j1"])),
                    self._axis(int(axes["j2"])),
                    self._axis(int(axes["j3"])),
                    self._axis(int(axes["j4"])),
                ]
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
                wrist_dir = (1.0 if self._button(int(buttons["wrist_rb"])) else 0.0) - (
                    1.0 if self._button(int(buttons["wrist_lb"])) else 0.0
                )
                lt = normalize_trigger(self._axis(int(axes["lt"])))
                rt = normalize_trigger(self._axis(int(axes["rt"])))
                grip_dir = rt - lt

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
    parser = argparse.ArgumentParser(description="RobotKOL Windows Xbox -> Teensy bridge")
    parser.add_argument("--port", default=None, help="COM port override, ornek COM5")
    parser.add_argument("--profile", type=Path, default=None, help="JSON profile path")
    parser.add_argument("--joystick-index", type=int, default=0, help="Pygame joystick index")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = load_profile(args.profile)
    port = args.port or profile.get("serial_port") or autodetect_teensy_port()
    link = TeensyLink(port, int(profile["baudrate"]))

    pygame.init()
    try:
        print(json.dumps(link.request({"cmd": "ping"}), ensure_ascii=False))
        print(json.dumps(link.request({"cmd": "scan_i2c"}), ensure_ascii=False))
        js = select_joystick(args.joystick_index)
        print(f"Joystick: {js.get_name()} | axes={js.get_numaxes()} buttons={js.get_numbuttons()}")
        WindowsXboxBridge(profile, js, link).run()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            link.send({"cmd": "stop"})
            link.send({"cmd": "en", "on": 0})
        except Exception:
            pass
        link.close()
        pygame.quit()


if __name__ == "__main__":
    main()
