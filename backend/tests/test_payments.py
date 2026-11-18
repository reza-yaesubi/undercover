from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException

from backend.models import Handler
from backend.workflow import begin_run

CLAIM = "CLM-1001"
DECISION_URL = f"/api/claims/{CLAIM}/decision"
PAY_URL = f"/api/claims/{CLAIM}/pay"
SIGN_OFF_URL = f"/api/claims/{CLAIM}/sign-off"


def decision_body(database, **overrides):
    run = begin_run(database, CLAIM)
    return {
        "thread_id": run.thread_id,
        "outcome": "approve",
        "payout": "420.00",
        "reason": [
            "The covered delay meets the waiting period.",
            "Receipts total $420.",
        ],
        "policy_sections": [3, 10],
        "calculation": "245.00 + 95.00 + 80.00 = 420.00; no deductible.",
        **overrides,
    }


def test_record_decision_and_reject_replacement(client, database):
    body = decision_body(database)
    response = client.post(DECISION_URL, json=body)
    assert response.status_code == 201
    assert response.json()["status"] == "decided"
    saved = response.json()["decision"]
    assert saved["payout"] == "420.00"
    assert saved["reason"] == body["reason"]
    assert saved["policy_sections"] == [3, 10]
    assert saved["recorded_at"]
    assert client.post(DECISION_URL, json=body).status_code == 409
    detail = client.get(f"/api/claims/{CLAIM}").json()
    assert detail["decision"] == saved
    assert detail["run"]["thread_id"] == body["thread_id"]


@pytest.mark.parametrize(
    "changes",
    [
        {"outcome": "unknown"},
        {"reason": ["Only one sentence."]},
        {"reason": ["A.", "B.", "C.", "D."]},
        {"reason": [" ", "Another sentence."]},
        {"policy_sections": [99]},
        {"policy_sections": []},
        {"payout": "-1.00"},
        {"outcome": "refer", "payout": "1.00"},
    ],
)
def test_invalid_decisions_never_persist(client, database, changes):
    body = decision_body(database, **changes)
    assert client.post(DECISION_URL, json=body).status_code == 422
    assert client.get(f"/api/claims/{CLAIM}").json()["decision"] is None


def test_missing_input_and_inactive_thread(client, database):
    body = decision_body(database)
    incomplete = {key: value for key, value in body.items() if key != "calculation"}
    assert client.post(DECISION_URL, json=incomplete).status_code == 422
    assert (
        client.post(DECISION_URL, json={**body, "thread_id": "another-run"}).status_code
        == 409
    )
    assert client.post("/api/claims/CLM-1002/decision", json=body).status_code == 409
    assert client.post("/api/claims/missing/decision", json=body).status_code == 404


@pytest.mark.parametrize("amount", ["420.00", "1000.00"])
def test_under_limit_payment_needs_no_sign_off(client, database, amount):
    response = client.post(DECISION_URL, json=decision_body(database, payout=amount))
    assert response.json()["status"] == "decided"
    paid = client.post(PAY_URL, json={"amount": amount})
    assert paid.status_code == 201
    assert paid.json()["payment"]["amount"] == amount
    assert paid.json()["payment"]["simulated"] is True
    assert client.get(f"/api/claims/{CLAIM}").json()["sign_off"] is None
    assert client.post(PAY_URL, json={"amount": amount}).json() == {
        "detail": "Claim already paid"
    }


def test_over_limit_guard_sign_off_and_exact_cents(client, database):
    response = client.post(DECISION_URL, json=decision_body(database, payout="1000.01"))
    assert response.json()["status"] == "waiting_for_sign_off"
    for _ in range(2):
        blocked = client.post(PAY_URL, json={"amount": "1000.01"})
        assert blocked.status_code == 409
        assert blocked.json() == {"detail": "Handler sign-off required"}
    split = client.post(PAY_URL, json={"amount": "1000.00"})
    assert split.status_code == 409
    assert split.json() == {"detail": "Amount does not match approval"}
    assert client.get(f"/api/claims/{CLAIM}").json()["payment"] is None

    approved = client.post(SIGN_OFF_URL, json={"handler_id": "HND-01"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "decided"
    assert approved.json()["sign_off"]["handler_id"] == "HND-01"
    assert approved.json()["sign_off"]["signed_off_at"]
    assert client.get(f"/api/claims/{CLAIM}").json()["payment"] is None
    assert client.post(PAY_URL, json={"amount": "1000.01"}).status_code == 201
    with database.connect() as connection:
        assert (
            connection.execute("SELECT amount_cents FROM payments").fetchone()[0]
            == 100001
        )


@pytest.mark.parametrize("outcome", ["approve", "decline", "refer"])
def test_non_payable_outcomes(client, database, outcome):
    assert client.post(PAY_URL, json={"amount": "1.00"}).status_code == 409
    body = decision_body(database, payout="0.00", outcome=outcome)
    assert client.post(DECISION_URL, json=body).status_code == 201
    assert client.post(PAY_URL, json={"amount": "0.00"}).status_code == 409
    assert client.post(SIGN_OFF_URL, json={"handler_id": "HND-01"}).status_code == 409


@pytest.mark.parametrize(
    "amount", ["-1", "NaN", "Infinity", "0.001", "10000000000000000"]
)
def test_invalid_payment_amount(client, amount):
    assert client.post(PAY_URL, json={"amount": amount}).status_code == 422
    assert client.post(PAY_URL, json={}).status_code == 422


def test_handler_validation_and_sign_off_state(client, database):
    assert client.post(SIGN_OFF_URL, json={"handler_id": "missing"}).status_code == 404
    handler = Handler(
        handler_id="HND-TEST", name="Not authorized", can_approve_over_limit=False
    )
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO records VALUES ('handler', ?, ?)",
            (handler.handler_id, handler.model_dump_json()),
        )
    assert (
        client.post(SIGN_OFF_URL, json={"handler_id": handler.handler_id}).status_code
        == 403
    )
    assert client.post(SIGN_OFF_URL, json={"handler_id": "HND-01"}).status_code == 409


def test_concurrent_payment_records_only_once(client, database):
    client.post(DECISION_URL, json=decision_body(database))

    def pay_once(_index):
        return client.post(PAY_URL, json={"amount": "420.00"}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(pay_once, range(2))) == [201, 409]
    with database.connect() as connection:
        assert connection.execute("SELECT count(*) FROM payments").fetchone()[0] == 1


def test_begin_run_rejects_duplicate_and_decided(client, database):
    body = decision_body(database)
    with pytest.raises(HTTPException, match="Claim is already running"):
        begin_run(database, CLAIM)
    client.post(DECISION_URL, json=body)
    with database.connect() as connection:
        connection.execute("UPDATE runs SET status = 'completed'")
    with pytest.raises(HTTPException, match="Claim is not waiting"):
        begin_run(database, CLAIM)
