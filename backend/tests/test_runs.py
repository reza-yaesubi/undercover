from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event

import pytest
from fastapi.testclient import TestClient

from backend import activity, reads, workflow
from backend.database import Database
from backend.main import create_app
from backend.runner import RunFailure, execute_run, fail_run
from backend.tests.pilot_data import draft_for, pilot_seed
from backend.workflow_models import DecisionInput, PaymentInput

CLAIM = "CLM-T420"


def save_decision(database, started):
    draft = draft_for(started.claim_id)
    return workflow.record_decision(
        database,
        started.claim_id,
        DecisionInput(**draft.model_dump(), thread_id=started.thread_id),
    )


def test_worker_does_not_block_health_or_duplicate_guard(tmp_path):
    database = Database(tmp_path / "runs.sqlite3")
    entered = Event()
    release = Event()

    def held_runner(_claim_id, _thread_id):
        entered.set()
        if not release.wait(10):
            raise RunFailure("Test worker was not released")
        raise RunFailure("Controlled worker failure")

    app = create_app(database, pilot_seed(), held_runner)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
        response = pool.submit(client.post, f"/api/claims/{CLAIM}/run")
        try:
            assert entered.wait(5)
            assert client.get("/api/health").json() == {"status": "ok"}
            running = client.get(f"/api/claims/{CLAIM}").json()
            assert running["claim"]["status"] == "in_progress"
            assert running["run"]["status"] == "running"
            assert (
                client.get(f"/api/claims/{CLAIM}/activity").json()["events"][0]["kind"]
                == "started"
            )
            duplicate = client.post(f"/api/claims/{CLAIM}/run")
            assert duplicate.status_code == 409
            assert duplicate.json() == {"detail": "Claim is already running"}
        finally:
            release.set()
        assert response.result().status_code == 202
        failed = client.get(f"/api/claims/{CLAIM}").json()
        assert failed["claim"]["status"] == "waiting"
        assert failed["run"]["error"] == "Controlled worker failure"
        retry = client.post(f"/api/claims/{CLAIM}/run")
        assert retry.json()["thread_id"] != running["run"]["thread_id"]
        events = client.get(f"/api/claims/{CLAIM}/activity").json()["events"]
        assert len({event["thread_id"] for event in events}) == 2
        assert [event["sequence"] for event in events] == sorted(
            event["sequence"] for event in events
        )
        assert client.post("/api/claims/missing/run").status_code == 404


@pytest.mark.parametrize(
    "mode", ["no_decision", "unpaid", "after_payment", "model_error"]
)
def test_failed_runs_preserve_work_and_redact_errors(database, mode, caplog):
    database.initialize(pilot_seed())
    started = workflow.begin_run(database, CLAIM)

    def runner(_claim_id, _thread_id):
        if mode == "model_error":
            raise RuntimeError("sensitive provider response")
        if mode != "no_decision":
            save_decision(database, started)
        if mode == "after_payment":
            workflow.pay(database, CLAIM, PaymentInput(amount=Decimal("420.00")))
            raise RunFailure("Failed after payment")
        return "Done"

    execute_run(database, runner, started)
    with database.connect() as connection:
        latest = workflow.latest_run(connection, CLAIM)
        assert latest is not None
        assert latest.status == "failed"
        assert latest.finished_at
        assert "sensitive provider response" not in str(latest.error)
        assert (workflow.stored_decision(connection, CLAIM) is not None) == (
            mode in {"unpaid", "after_payment"}
        )
        assert (workflow.stored_payment(connection, CLAIM) is not None) == (
            mode == "after_payment"
        )
    assert "failed" in caplog.text


@pytest.mark.parametrize(
    "claim_id", ["CLM-T420", "CLM-T100001", "CLM-TDECLINE", "CLM-TREFER"]
)
def test_completed_runs_and_restart_persistence(database, claim_id):
    seed = pilot_seed()
    database.initialize(seed)
    started = workflow.begin_run(database, claim_id)

    def runner(_claim_id, _thread_id):
        decision = save_decision(database, started).decision
        if decision.outcome == "approve" and 0 < decision.payout <= 1000:
            workflow.pay(database, claim_id, PaymentInput(amount=decision.payout))
        return "Recorded"

    execute_run(database, runner, started)
    if claim_id == "CLM-T100001":
        workflow.sign_off(database, claim_id, "HND-01")
        workflow.pay(database, claim_id, PaymentInput(amount=Decimal("1000.01")))
    saved_detail = reads.get_claim(database, claim_id).model_dump(mode="json")
    saved_activity = activity.list_activity(database, claim_id).model_dump(mode="json")
    interrupted = workflow.begin_run(database, "CLM-TBAG")
    reopened = Database(database.path)
    with TestClient(create_app(reopened, seed)) as client:
        detail = client.get(f"/api/claims/{claim_id}").json()
        assert detail == saved_detail
        assert client.get(f"/api/claims/{claim_id}/activity").json() == saved_activity
        assert detail["run"]["status"] == "completed"
        assert detail["decision"]["outcome"] == draft_for(claim_id).outcome
        if claim_id in {"CLM-T420", "CLM-T100001"}:
            assert detail["payment"]["simulated"] is True
        restarted = client.get("/api/claims/CLM-TBAG").json()
        assert restarted["claim"]["status"] == "waiting"
        assert restarted["run"]["status"] == "failed"
        assert "restart" in restarted["run"]["error"]
        assert client.post(f"/api/claims/{claim_id}/run").status_code == 409
        fail_run(database, interrupted, "Late worker failure")
        assert (
            client.get("/api/claims/CLM-TBAG").json()["run"]["error"]
            == restarted["run"]["error"]
        )


def test_activity_rejects_stale_thread_and_unknown_claim(client, database):
    started = workflow.begin_run(database, "CLM-1001")
    path = "/api/claims/CLM-1001/activity"
    event = {
        "thread_id": started.thread_id,
        "kind": "tool_result",
        "message": "Read evidence.",
    }
    response = client.post(path, json=event)
    assert response.status_code == 201
    assert response.json()["created_at"]
    assert client.post(path, json={**event, "thread_id": "stale"}).status_code == 409
    assert client.get("/api/claims/missing/activity").status_code == 404
    fail_run(database, started, "Stopped for test")
    assert client.post(path, json=event).status_code == 409
