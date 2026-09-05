from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FixtureConfig:
    id: int
    name: str
    address: int
    red: int
    green: int
    blue: int
    dimmer: int | None = None
    dimmer_on: int = 255
    fixed_channels: tuple[tuple[int, int], ...] = ()

    @property
    def highest_channel(self) -> int:
        offsets = [self.red, self.green, self.blue]
        if self.dimmer is not None:
            offsets.append(self.dimmer)
        offsets.extend(offset for offset, _ in self.fixed_channels)
        return self.address + max(offsets)


@dataclass(frozen=True)
class Settings:
    port: str
    refresh_hz: float
    simulation: bool
    fixtures: tuple[FixtureConfig, ...]

    @property
    def universe_size(self) -> int:
        return max(f.highest_channel for f in self.fixtures)


def _bool_env(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings(base_dir: Path | None = None) -> Settings:
    root = base_dir or Path(__file__).resolve().parents[1]
    fixture_path = Path(os.getenv("DMX_FIXTURES_FILE", "config/fixtures.json"))
    if not fixture_path.is_absolute():
        fixture_path = root / fixture_path

    with fixture_path.open(encoding="utf-8") as handle:
        raw = json.load(handle)

    fixtures: list[FixtureConfig] = []
    ids: set[int] = set()
    occupied: set[int] = set()
    for item in raw.get("fixtures", []):
        channels = item["channels"]
        fixed_channels = tuple(
            (int(offset), int(value))
            for offset, value in item.get("fixed_channels", {}).items()
        )
        fixture = FixtureConfig(
            id=int(item["id"]),
            name=str(item["name"]),
            address=int(item["address"]),
            red=int(channels["red"]),
            green=int(channels["green"]),
            blue=int(channels["blue"]),
            dimmer=(int(channels["dimmer"]) if "dimmer" in channels else None),
            dimmer_on=int(item.get("dimmer_on", 255)),
            fixed_channels=fixed_channels,
        )
        if fixture.id in ids:
            raise ValueError(f"Fixture-ID {fixture.id} ist doppelt vergeben")
        if not 1 <= fixture.address <= 512:
            raise ValueError(f"DMX-Adresse {fixture.address} liegt nicht zwischen 1 und 512")
        if fixture.highest_channel > 512:
            raise ValueError(f"{fixture.name} belegt einen Kanal oberhalb von 512")
        offsets = [fixture.red, fixture.green, fixture.blue]
        if fixture.dimmer is not None:
            offsets.append(fixture.dimmer)
        offsets.extend(offset for offset, _ in fixture.fixed_channels)
        if min(offsets) < 0 or len(offsets) != len(set(offsets)):
            raise ValueError(f"Ungültige Kanalzuordnung für {fixture.name}")
        if not 0 <= fixture.dimmer_on <= 255 or any(
            not 0 <= value <= 255 for _, value in fixture.fixed_channels
        ):
            raise ValueError(f"DMX-Werte für {fixture.name} müssen zwischen 0 und 255 liegen")
        fixture_channels = {fixture.address + offset for offset in offsets}
        if occupied & fixture_channels:
            raise ValueError(f"DMX-Kanäle von {fixture.name} überschneiden sich")
        occupied |= fixture_channels
        ids.add(fixture.id)
        fixtures.append(fixture)

    if len(fixtures) != 2:
        raise ValueError("Diese Anwendung erwartet genau zwei Scheinwerfer")

    refresh_hz = float(os.getenv("DMX_REFRESH_HZ", "30"))
    if not 1 <= refresh_hz <= 44:
        raise ValueError("DMX_REFRESH_HZ muss zwischen 1 und 44 liegen")

    return Settings(
        port=os.getenv("DMX_PORT", "/dev/ttyAMA0"),
        refresh_hz=refresh_hz,
        simulation=_bool_env(os.getenv("DMX_SIMULATION")),
        fixtures=tuple(fixtures),
    )
