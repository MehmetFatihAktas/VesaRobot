from __future__ import annotations

import argparse
import cmd
import json
import shlex
import threading
import time
from typing import Any

from teensy_link import TeensyLink


class ManualShell(cmd.Cmd):
    intro = (
        "RobotKOL manual CLI\n"
        "Komutlar: ping, scan, diag, en 0|1, move <4 step>, move_deg <4 deg> [v] [a],\n"
        "servo <gripper> [wrist], stop, home, status, telemetry on|off, quit"
    )
    prompt = "robotkol> "

    def __init__(self, link: TeensyLink):
        super().__init__()
        self.link = link
        self._telemetry_print = False
        self._telemetry_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self._telemetry_thread.start()

    def _telemetry_loop(self) -> None:
        while True:
            if self._telemetry_print:
                msg = self.link.latest_telemetry
                if msg and {"enc_deg", "joint_deg", "en"}.issubset(msg.keys()):
                    print(
                        "\nTLM",
                        json.dumps(
                            {
                                "t": msg.get("t"),
                                "en": msg.get("en"),
                                "enc_deg": [round(float(v), 2) for v in msg.get("enc_deg", [])],
                                "joint_deg": [round(float(v), 2) for v in msg.get("joint_deg", [])],
                            },
                            ensure_ascii=False,
                        ),
                    )
                    print(self.prompt, end="", flush=True)
                time.sleep(0.5)
                continue
            time.sleep(0.1)

    def _print_response(self, payload: dict[str, Any]) -> None:
        try:
            msg = self.link.request(payload)
            print(json.dumps(msg, indent=2, ensure_ascii=False))
        except TimeoutError as exc:
            print(f"HATA: {exc}")

    def do_ping(self, arg: str) -> None:
        self._print_response({"cmd": "ping"})

    def do_scan(self, arg: str) -> None:
        self._print_response({"cmd": "scan_i2c"})

    def do_diag(self, arg: str) -> None:
        self._print_response({"cmd": "diag"})

    def do_en(self, arg: str) -> None:
        value = arg.strip().lower()
        if value not in {"0", "1", "on", "off"}:
            print("KULLANIM: en 0|1")
            return
        self._print_response({"cmd": "en", "on": 1 if value in {"1", "on"} else 0})

    def do_move(self, arg: str) -> None:
        parts = shlex.split(arg)
        if len(parts) not in {4, 6}:
            print("KULLANIM: move j1 j2 j3 j4 [v a]")
            return
        payload: dict[str, Any] = {"cmd": "move", "j": [int(p) for p in parts[:4]]}
        if len(parts) == 6:
            payload["v"] = float(parts[4])
            payload["a"] = float(parts[5])
        self._print_response(payload)

    def do_move_deg(self, arg: str) -> None:
        parts = shlex.split(arg)
        if len(parts) not in {4, 6}:
            print("KULLANIM: move_deg j1 j2 j3 j4 [v a]")
            return
        payload: dict[str, Any] = {"cmd": "move_deg", "j": [float(p) for p in parts[:4]]}
        if len(parts) == 6:
            payload["v"] = float(parts[4])
            payload["a"] = float(parts[5])
        self._print_response(payload)

    def do_servo(self, arg: str) -> None:
        parts = shlex.split(arg)
        if len(parts) not in {1, 2}:
            print("KULLANIM: servo gripper [wrist]")
            return
        payload: dict[str, Any] = {"cmd": "servo", "s": [int(parts[0])]}
        if len(parts) == 2:
            payload["s"].append(int(parts[1]))
        self._print_response(payload)

    def do_stop(self, arg: str) -> None:
        self._print_response({"cmd": "stop"})

    def do_home(self, arg: str) -> None:
        self._print_response({"cmd": "home"})

    def do_status(self, arg: str) -> None:
        tlm = self.link.latest_telemetry
        if tlm is None:
            print("Henüz telemetri yok.")
            return
        print(json.dumps(tlm, indent=2, ensure_ascii=False))

    def do_telemetry(self, arg: str) -> None:
        value = arg.strip().lower()
        if value not in {"on", "off"}:
            print("KULLANIM: telemetry on|off")
            return
        self._telemetry_print = value == "on"

    def do_quit(self, arg: str) -> bool:
        return True

    def do_exit(self, arg: str) -> bool:
        return True

    def emptyline(self) -> None:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RobotKOL Teensy manual CLI")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Teensy serial port")
    parser.add_argument("--baudrate", type=int, default=115200, help="Serial baudrate")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    link = TeensyLink(args.port, args.baudrate)
    try:
        ManualShell(link).cmdloop()
    finally:
        link.close()


if __name__ == "__main__":
    main()
