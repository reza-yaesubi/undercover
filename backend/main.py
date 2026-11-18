"""The UnderCover backend."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend import reads
from backend.database import DEFAULT_DATABASE, Database
from backend.models import (
    ClaimDetail,
    ClaimQueue,
    HandlerList,
    Instructions,
    PolicyWording,
)
from backend.run_routes import add_run_routes
from backend.runner import AgentRunner, live_runner, recover_interrupted_runs
from backend.seed import SeedData, load_seed
from backend.workflow_routes import add_workflow_routes


def create_app(
    database: Database | None = None,
    seed: SeedData | None = None,
    runner: AgentRunner = live_runner,
) -> FastAPI:
    """Create the pilot API with injectable storage for isolated tests."""
    database = database or Database(DEFAULT_DATABASE)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        database.initialize(seed or load_seed())
        recover_interrupted_runs(database)
        yield

    app = FastAPI(title="UnderCover", lifespan=lifespan)

    @app.get("/api/health", operation_id="health")
    def health() -> dict[str, str]:
        """Check that the backend is running."""
        return {"status": "ok"}

    @app.get("/api/claims", operation_id="list_claims")
    def list_claims() -> ClaimQueue:
        """List the claims queue and its current statuses."""
        return reads.list_claims(database)

    @app.get("/api/claims/{claim_id}", operation_id="get_claim")
    def get_claim(claim_id: str) -> ClaimDetail:
        """Read a claim with its policy, customer history and workflow records."""
        return reads.get_claim(database, claim_id)

    @app.get("/api/policy-wording", operation_id="get_policy_wording")
    def get_policy_wording() -> PolicyWording:
        """Read the full policy wording used by the pilot."""
        return reads.get_wording(database)

    @app.get("/api/agent/instructions", operation_id="get_agent_instructions")
    def get_agent_instructions() -> Instructions:
        """Read the agent instructions and pilot payment limit."""
        return reads.get_instructions(database)

    @app.get("/api/handlers", operation_id="list_handlers")
    def list_handlers() -> HandlerList:
        """List the handlers available for sign-off."""
        return reads.list_handlers(database)

    add_workflow_routes(app, database)
    add_run_routes(app, database, runner)
    return app


app = create_app()
