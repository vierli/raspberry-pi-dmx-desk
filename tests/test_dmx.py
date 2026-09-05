from pathlib import Path

import pytest

from app.config import load_settings
from app.dmx import DMXUniverse, parse_hex_color


def settings():
    return load_settings(Path(__file__).resolve().parents[1])


def test_default_seven_channel_fixture_mapping():
    config = settings()
    universe = DMXUniverse(config.fixtures, config.universe_size)
    universe.update_fixture(1, enabled=True, color="#123456")
    universe.update_fixture(2, enabled=True, color="#abcdef")

    assert universe.frame() == bytes(
        [
            0,  # DMX start code
            255, 0x12, 0x34, 0x56, 0, 0, 0,  # fixture 1: dimmer, RGB, strobe, mode, speed
            255, 0xAB, 0xCD, 0xEF, 0, 0, 0,  # fixture 2
        ]
    )


def test_blackout_preserves_state_but_zeros_output():
    config = settings()
    universe = DMXUniverse(config.fixtures, config.universe_size)
    universe.update_fixture(1, enabled=True, color="#ff8000")
    universe.set_blackout(True)

    assert universe.frame() == bytes(15)
    assert universe.snapshot()["fixtures"][0]["enabled"] is True


@pytest.mark.parametrize("value", ["red", "#12345", "#xyzxyz", "123456"])
def test_invalid_colors_are_rejected(value):
    with pytest.raises(ValueError):
        parse_hex_color(value)
