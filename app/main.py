from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings, load_settings
from .dmx import DMXController, DMXUniverse


class FixtureUpdate(BaseModel):
    enabled: bool | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class AllUpdate(BaseModel):
    enabled: bool
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class BlackoutUpdate(BaseModel):
    enabled: bool


def create_app(settings: Settings | None = None, controller: DMXController | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()
    universe = controller.universe if controller else DMXUniverse(
        resolved_settings.fixtures, resolved_settings.universe_size
    )
    resolved_controller = controller or DMXController(resolved_settings, universe)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        resolved_controller.start()
        yield
        resolved_controller.stop()

    app = FastAPI(
        title="DMX Desk",
        description="Lokale Steuerung für zwei RGB-DMX-Scheinwerfer",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.state.controller = resolved_controller
    app.state.universe = universe

    @app.get("/api/state")
    async def get_state() -> dict:
        return {**universe.snapshot(), "dmx": resolved_controller.status()}

    @app.patch("/api/fixtures/{fixture_id}")
    async def update_fixture(fixture_id: int, update: FixtureUpdate) -> dict:
        if update.enabled is None and update.color is None:
            raise HTTPException(status_code=422, detail="Mindestens ein Wert ist erforderlich")
        try:
            universe.update_fixture(fixture_id, enabled=update.enabled, color=update.color)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Scheinwerfer nicht gefunden") from exc
        return {**universe.snapshot(), "dmx": resolved_controller.status()}

    @app.post("/api/all")
    async def update_all(update: AllUpdate) -> dict:
        universe.set_all(update.enabled, update.color)
        return {**universe.snapshot(), "dmx": resolved_controller.status()}

    @app.post("/api/blackout")
    async def update_blackout(update: BlackoutUpdate) -> dict:
        universe.set_blackout(update.enabled)
        return {**universe.snapshot(), "dmx": resolved_controller.status()}

    static_dir = Path(__file__).resolve().parent / "static"

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app


app = create_app()

