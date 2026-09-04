from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings, load_settings
from app.dmx import DMXController, DMXUniverse
from app.main import create_app


def make_client() -> TestClient:
    base = load_settings(Path(__file__).resolve().parents[1])
    settings = Settings(
        port=base.port,
        refresh_hz=base.refresh_hz,
        simulation=True,
        fixtures=base.fixtures,
    )
    universe = DMXUniverse(settings.fixtures, settings.universe_size)
    controller = DMXController(settings, universe)
    return TestClient(create_app(settings, controller))


def test_fixture_can_be_switched_and_colored():
    with make_client() as client:
        response = client.patch("/api/fixtures/1", json={"enabled": True, "color": "#102030"})
        assert response.status_code == 200
        fixture = response.json()["fixtures"][0]
        assert fixture["enabled"] is True
        assert fixture["color"] == "#102030"


def test_blackout_endpoint():
    with make_client() as client:
        response = client.post("/api/blackout", json={"enabled": True})
        assert response.status_code == 200
        assert response.json()["blackout"] is True


def test_unknown_fixture_returns_404():
    with make_client() as client:
        response = client.patch("/api/fixtures/99", json={"enabled": True})
        assert response.status_code == 404

