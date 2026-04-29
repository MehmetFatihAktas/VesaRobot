from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any, Optional

import serial


class TeensyLink:
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.05):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        self._messages: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._running = True
        self._latest_telemetry: Optional[dict[str, Any]] = None
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    @property
    def latest_telemetry(self) -> Optional[dict[str, Any]]:
        return self._latest_telemetry

    def close(self) -> None:
        self._running = False
        try:
            self.ser.close()
        except Exception:
            pass

    def _reader_loop(self) -> None:
        while self._running:
            try:
                line = self.ser.readline()
            except serial.SerialException:
                break

            if not line:
                continue

            try:
                msg = json.loads(line.decode("utf-8", errors="ignore").strip())
            except json.JSONDecodeError:
                continue

            if {"enc_deg", "pos_steps", "joint_deg"}.issubset(msg.keys()):
                self._latest_telemetry = msg

            self._messages.put(msg)

    def send(self, payload: dict[str, Any]) -> None:
        wire = json.dumps(payload, separators=(",", ":")) + "\n"
        self.ser.write(wire.encode("utf-8"))

    def drain_messages(self) -> None:
        while True:
            try:
                self._messages.get_nowait()
            except queue.Empty:
                return

    def get_message(self, timeout: float = 0.0) -> Optional[dict[str, Any]]:
        try:
            return self._messages.get(timeout=timeout)
        except queue.Empty:
            return None

    def request(self, payload: dict[str, Any], timeout: float = 1.0) -> dict[str, Any]:
        expected = "pong" if payload.get("cmd") == "ping" else payload.get("cmd")
        self.drain_messages()
        self.send(payload)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            msg = self.get_message(timeout=0.1)
            if msg is None:
                continue
            if "ack" in msg and msg.get("msg") == expected:
                return msg

        raise TimeoutError(f"Timed out waiting for ack for {payload!r}")
