"""Run one agent in a worker and make completion or failure explicit."""

import logging
from collections.abc import Callable

import httpx

from agent.main import run
from backend import workflow
from backend.activity import append_event
from backend.database import Database, claim_row, record, timestamp
from backend.models import Company
from backend.workflow_models import ActivityInput, RunStart

AgentRunner = Callable[[str, str], str]
logger = logging.getLogger(__name__)


class RunFailure(RuntimeError):
    """A safe, handler-readable run failure."""


def live_runner(claim_id: str, thread_id: str) -> str:
    return run(claim_id, thread_id)


def finish_run(database: Database, started: RunStart) -> None:
    with database.write() as connection:
        decision = workflow.stored_decision(connection, started.claim_id)
        if decision is None:
            raise RunFailure("Agent finished without storing a decision.")
        company = record(connection, "company", "undercover", Company)
        if (
            decision.outcome == "approve"
            and 0 < decision.payout <= company.payout_approval_limit
            and workflow.stored_payment(connection, started.claim_id) is None
        ):
            raise RunFailure("Approved claim has no simulated payment. Retry payment.")
        updated = connection.execute(
            """UPDATE runs SET status = 'completed', finished_at = ?
               WHERE thread_id = ? AND status = 'running'""",
            (timestamp(), started.thread_id),
        )
        if updated.rowcount != 1:
            raise RunFailure("The agent run is no longer active.")
        append_event(
            connection,
            started.claim_id,
            ActivityInput(
                thread_id=started.thread_id,
                kind="completed",
                message="Agent run completed.",
            ),
        )


def fail_run(database: Database, started: RunStart, message: str) -> None:
    logger.error(
        "Run %s for %s failed: %s", started.thread_id, started.claim_id, message
    )
    with database.write() as connection:
        updated = connection.execute(
            """UPDATE runs SET status = 'failed', finished_at = ?, error = ?
               WHERE thread_id = ? AND status = 'running'""",
            (timestamp(), message, started.thread_id),
        )
        if updated.rowcount != 1:
            logger.warning(
                "Run %s was already stopped; preserving its state", started.thread_id
            )
            return
        claim_row(connection, started.claim_id)
        if workflow.stored_decision(connection, started.claim_id) is None:
            connection.execute(
                "UPDATE claims SET status = 'waiting' WHERE claim_id = ?",
                (started.claim_id,),
            )
        append_event(
            connection,
            started.claim_id,
            ActivityInput(thread_id=started.thread_id, kind="error", message=message),
        )


def public_error(error: Exception) -> str:
    if isinstance(error, RunFailure):
        return str(error)
    if isinstance(error, httpx.HTTPStatusError):
        return f"Backend rejected an agent request (HTTP {error.response.status_code})."
    return (
        f"Agent run failed ({type(error).__name__}). "
        "Check the model configuration and backend log before retrying."
    )


def execute_run(database: Database, runner: AgentRunner, started: RunStart) -> None:
    try:
        runner(started.claim_id, started.thread_id)
        finish_run(database, started)
    except Exception as error:
        fail_run(database, started, public_error(error))


def recover_interrupted_runs(database: Database) -> None:
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT claim_id, thread_id FROM runs WHERE status = 'running'"
        ).fetchall()
    for row in rows:
        fail_run(
            database,
            RunStart(claim_id=row["claim_id"], thread_id=row["thread_id"]),
            "Agent run was interrupted by a backend restart. Retry explicitly.",
        )
