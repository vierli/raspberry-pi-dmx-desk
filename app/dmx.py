from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from .config import FixtureConfig, Settings


class SerialPort(Protocol):
    break_condition: bool

    def write(self, data: bytes) -> int: ...
    def close(self) -> None: ...


@dataclass
class FixtureState:
    enabled: bool = False
    color: str = "#ffffff"


def parse_hex_color(value: str) -> tuple[int, int, int]:
    normalized = value.strip().lower()
    if len(normalized) != 7 or not normalized.startswith("#"):
        raise ValueError("Farbe muss im Format #RRGGBB angegeben werden")
    try:
        return tuple(int(normalized[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError("Farbe muss im Format #RRGGBB angegeben werden") from exc


class DMXUniverse:
    def __init__(self, fixtures: tuple[FixtureConfig, ...], size: int):
        self.fixtures = {fixture.id: fixture for fixture in fixtures}
        self.states = {fixture.id: FixtureState() for fixture in fixtures}
        self.size = size
        self.blackout = False
        self._lock = threading.Lock()

    def update_fixture(
        self, fixture_id: int, *, enabled: bool | None = None, color: str | None = None
    ) -> None:
        with self._lock:
            if fixture_id not in self.states:
                raise KeyError(fixture_id)
            state = self.states[fixture_id]
            if enabled is not None:
                state.enabled = enabled
            if color is not None:
                parse_hex_color(color)
                state.color = color.lower()

    def set_all(self, enabled: bool, color: str | None = None) -> None:
        if color is not None:
            parse_hex_color(color)
        with self._lock:
            for state in self.states.values():
                state.enabled = enabled
                if color is not None:
                    state.color = color.lower()

    def set_blackout(self, enabled: bool) -> None:
        with self._lock:
            self.blackout = enabled

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "blackout": self.blackout,
                "fixtures": [
                    {
                        "id": fixture.id,
                        "name": fixture.name,
                        "address": fixture.address,
                        "last_channel": fixture.highest_channel,
                        "enabled": self.states[fixture.id].enabled,
                        "color": self.states[fixture.id].color,
                    }
                    for fixture in self.fixtures.values()
                ],
            }

    def frame(self, force_blackout: bool = False) -> bytes:
        channels = bytearray(self.size + 1)  # Byte 0 is the DMX start code.
        with self._lock:
            blackout = self.blackout or force_blackout
            for fixture_id, fixture in self.fixtures.items():
                state = self.states[fixture_id]
                active = state.enabled and not blackout
                red, green, blue = parse_hex_color(state.color) if active else (0, 0, 0)
                channels[fixture.address + fixture.red] = red
                channels[fixture.address + fixture.green] = green
                channels[fixture.address + fixture.blue] = blue
                if fixture.dimmer is not None:
                    channels[fixture.address + fixture.dimmer] = fixture.dimmer_on if active else 0
        return bytes(channels)


class DMXController:
    """Continuously transmits DMX512 frames over a UART-backed RS-485 adapter."""

    def __init__(
        self,
        settings: Settings,
        universe: DMXUniverse,
        serial_factory: Callable[[str], SerialPort] | None = None,
    ):
        self.settings = settings
        self.universe = universe
        self._serial_factory = serial_factory or self._open_serial
        self._serial: SerialPort | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._status_lock = threading.Lock()
        self._connected = settings.simulation
        self._last_error: str | None = None

    @staticmethod
    def _open_serial(port: str) -> SerialPort:
        import serial

        return serial.Serial(
            port=port,
            baudrate=250_000,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_TWO,
            timeout=0,
            write_timeout=0.5,
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="dmx-output", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._serial:
            try:
                for _ in range(3):
                    self._send_frame(self.universe.frame(force_blackout=True))
            except Exception:
                pass
            self._serial.close()
            self._serial = None

    def status(self) -> dict:
        with self._status_lock:
            return {
                "connected": self._connected,
                "mode": "simulation" if self.settings.simulation else "hardware",
                "port": self.settings.port,
                "refresh_hz": self.settings.refresh_hz,
                "last_error": self._last_error,
            }

    def _set_status(self, connected: bool, error: str | None = None) -> None:
        with self._status_lock:
            self._connected = connected
            self._last_error = error

    def _send_frame(self, frame: bytes) -> None:
        assert self._serial is not None
        self._serial.break_condition = True
        time.sleep(0.0001)  # DMX break: >= 88 microseconds.
        self._serial.break_condition = False
        time.sleep(0.000012)  # Mark-after-break: >= 8 microseconds.
        self._serial.write(frame)

    def _run(self) -> None:
        interval = 1 / self.settings.refresh_hz
        if self.settings.simulation:
            while not self._stop.wait(interval):
                pass
            return

        while not self._stop.is_set():
            started = time.monotonic()
            try:
                if self._serial is None:
                    self._serial = self._serial_factory(self.settings.port)
                self._send_frame(self.universe.frame())
                self._set_status(True)
            except Exception as exc:
                self._set_status(False, str(exc))
                if self._serial is not None:
                    try:
                        self._serial.close()
                    except Exception:
                        pass
                    self._serial = None
                self._stop.wait(2)
                continue
            remaining = interval - (time.monotonic() - started)
            if remaining > 0:
                self._stop.wait(remaining)
