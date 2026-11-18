from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.database import record
from backend.models import Company, Handler
from backend.seed import DATA_DIR, load_seed


def test_seeded_queue_and_complete_detail(client):
    queue = client.get("/api/claims")
    assert queue.status_code == 200
    body = queue.json()
    assert body["total"] == 25
    assert {claim["status"] for claim in body["claims"]} == {"waiting"}
    assert {claim["claim_id"] for claim in body["claims"]} == {
        claim.claim_id for claim in load_seed().claims
    }

    detail = client.get("/api/claims/CLM-1001").json()
    assert detail["claim"]["policy_id"] == "POL-2001"
    assert detail["claim"]["amount_claimed"] == 420
    assert len(detail["claim"]["items"]) == 3
    assert len(detail["claim"]["documents"]) == 4
    assert detail["policy"]["plan"] == "premium"
    assert detail["plan"]["trip_delay_max"] == 800
    assert detail["customer"]["previous_claims"][0]["claim_id"] == "CLM-0412"
    assert detail["decision"] is None
    assert detail["sign_off"] is None
    assert detail["payment"] is None
    assert detail["run"] is None


def test_reinitializing_preserves_work(client, database):
    with database.connect() as connection:
        connection.execute(
            "UPDATE claims SET status = 'decided' WHERE claim_id = 'CLM-1001'"
        )
    database.initialize(load_seed())
    assert client.get("/api/claims").json()["total"] == 25
    assert client.get("/api/claims/CLM-1001").json()["claim"]["status"] == "decided"


def test_only_allowlisted_data_is_read(monkeypatch, client, database):
    read_text = Path.read_text
    paths = []

    def track_read(path, *args, **kwargs):
        assert path.parent == DATA_DIR
        paths.append(path.name)
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", track_read)
    seed = load_seed()
    assert set(paths) == {
        "claims.json",
        "policies.json",
        "customers.json",
        "plans.json",
        "handlers.json",
        "company.json",
        "policy_wording.md",
    }
    assert len(seed.plans.plans) == 3
    assert len(seed.handlers) == 3
    with database.connect() as connection:
        company = record(connection, "company", "undercover", Company)
    assert set(company.model_dump()) == {
        "currency",
        "payout_approval_limit",
        "policy_wording_version",
    }
    assert "CLM-1901" not in client.get("/api/claims").text


def test_wording_instructions_and_handlers(client):
    wording = client.get("/api/policy-wording")
    assert wording.status_code == 200
    assert wording.json() == {"version": "2026.1", "content": load_seed().wording}
    instructions = client.get("/api/agent/instructions").json()
    assert instructions["currency"] == "USD"
    assert instructions["payout_approval_limit"] == "1000.00"
    assert "record_decision" in instructions["content"]
    assert "repeat_claim_review" not in instructions["content"]
    handlers = client.get("/api/handlers").json()["handlers"]
    assert [handler["handler_id"] for handler in handlers] == [
        "HND-01",
        "HND-02",
        "HND-03",
    ]


def test_read_only_and_missing_records(client, database):
    assert (
        client.put("/api/agent/instructions", json={"content": "changed"}).status_code
        == 405
    )
    response = client.get("/api/claims/CLM-MISSING")
    assert response.status_code == 404
    assert response.json() == {"detail": "Claim not found"}
    assert client.get("/data/claims.json").status_code == 404
    with database.connect() as connection, pytest.raises(HTTPException) as error:
        record(connection, "handler", "missing", Handler)
    assert error.value.status_code == 404


def test_only_purchased_add_ons_are_in_claim_context(client):
    for claim in load_seed().claims:
        detail = client.get(f"/api/claims/{claim.claim_id}").json()
        assert {addon["add_on"] for addon in detail["plan"]["add_ons"]} == set(
            detail["policy"]["add_ons"]
        )
