"""Start background runs and expose their operational activity."""

from fastapi import BackgroundTasks, FastAPI

from backend import activity, workflow
from backend.database import Database
from backend.runner import AgentRunner, execute_run
from backend.workflow_models import Activity, ActivityInput, ActivityList, RunStart


def add_run_routes(app: FastAPI, database: Database, runner: AgentRunner) -> None:
    @app.post(
        "/api/claims/{claim_id}/run", operation_id="start_claim_run", status_code=202
    )
    def start_claim_run(claim_id: str, background_tasks: BackgroundTasks) -> RunStart:
        """Start a waiting claim in a worker without blocking the API."""
        started = workflow.begin_run(database, claim_id)
        background_tasks.add_task(execute_run, database, runner, started)
        return started

    @app.get("/api/claims/{claim_id}/activity", operation_id="get_claim_activity")
    def get_claim_activity(claim_id: str) -> ActivityList:
        """Read ordered activity across a claim's run attempts."""
        return activity.list_activity(database, claim_id)

    @app.post(
        "/api/claims/{claim_id}/activity",
        operation_id="record_claim_activity",
        status_code=201,
    )
    def record_claim_activity(claim_id: str, event: ActivityInput) -> Activity:
        """Record a step for the claim's current running thread."""
        return activity.record_activity(database, claim_id, event)
