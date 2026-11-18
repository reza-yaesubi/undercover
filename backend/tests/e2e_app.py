"""Isolated test server; never selected by the normal development entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI

from agent.main import run
from agent.tests.stubs import scripted_model
from backend.database import Database
from backend.main import create_app as pilot_app
from backend.runner import RunFailure
from backend.tests.pilot_data import pilot_seed


def create_app() -> FastAPI:
    storage = TemporaryDirectory(prefix="undercover-e2e-")
    database = Database(Path(storage.name) / "pilot.sqlite3")
    attempts: dict[str, int] = {}

    def scripted_runner(claim_id: str, thread_id: str) -> str:
        attempts[claim_id] = attempts.get(claim_id, 0) + 1
        if claim_id == "CLM-TBAG" and attempts[claim_id] == 1:
            raise RunFailure("Simulated agent failure. Retry this claim explicitly.")
        return run(claim_id, thread_id, scripted_model(claim_id, delay=2))

    app = pilot_app(database, pilot_seed(), scripted_runner)
    pilot_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with storage:
            async with pilot_lifespan(app):
                yield

    app.router.lifespan_context = lifespan
    return app
