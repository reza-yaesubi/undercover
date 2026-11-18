"""Atomic claim transitions and the simulated payment guard."""

import re
import sqlite3
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from backend.activity import append_event
from backend.database import Database, claim_row, record, timestamp
from backend.models import Company, Handler, PolicyWording
from backend.workflow_models import (
    ActivityInput,
    Decision,
    DecisionInput,
    DecisionResult,
    Payment,
    PaymentInput,
    PaymentResult,
    QueueStatus,
    Run,
    RunStart,
    SignOff,
    SignOffResult,
    cents,
)


def latest_run(connection: sqlite3.Connection, claim_id: str) -> Run | None:
    row = connection.execute(
        "SELECT * FROM runs WHERE claim_id = ? ORDER BY run_id DESC LIMIT 1",
        (claim_id,),
    ).fetchone()
    return Run.model_validate(dict(row)) if row else None


def stored_decision(connection: sqlite3.Connection, claim_id: str) -> Decision | None:
    row = connection.execute(
        "SELECT body FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    return Decision.model_validate_json(row["body"]) if row else None


def stored_sign_off(connection: sqlite3.Connection, claim_id: str) -> SignOff | None:
    row = connection.execute(
        "SELECT * FROM sign_offs WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    return SignOff.model_validate(dict(row)) if row else None


def stored_payment(connection: sqlite3.Connection, claim_id: str) -> Payment | None:
    row = connection.execute(
        "SELECT * FROM payments WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        return None
    return Payment(
        amount=Decimal(row["amount_cents"]) / 100,
        paid_at=row["paid_at"],
        simulated=True,
    )


def begin_run(database: Database, claim_id: str) -> RunStart:
    with database.write() as connection:
        claim = claim_row(connection, claim_id)
        run = latest_run(connection, claim_id)
        if run and run.status == "running":
            raise HTTPException(status_code=409, detail="Claim is already running")
        if claim["status"] != "waiting" or stored_decision(connection, claim_id):
            raise HTTPException(status_code=409, detail="Claim is not waiting")
        thread_id = str(uuid4())
        connection.execute(
            """INSERT INTO runs (thread_id, claim_id, status, started_at)
               VALUES (?, ?, 'running', ?)""",
            (thread_id, claim_id, timestamp()),
        )
        connection.execute(
            "UPDATE claims SET status = 'in_progress' WHERE claim_id = ?", (claim_id,)
        )
        append_event(
            connection,
            claim_id,
            ActivityInput(
                thread_id=thread_id, kind="started", message="Agent run started."
            ),
        )
    return RunStart(claim_id=claim_id, thread_id=thread_id)


def record_decision(
    database: Database, claim_id: str, decision: DecisionInput
) -> DecisionResult:
    with database.write() as connection:
        claim_row(connection, claim_id)
        run = latest_run(connection, claim_id)
        if (
            run is None
            or run.status != "running"
            or run.thread_id != decision.thread_id
            or stored_decision(connection, claim_id) is not None
        ):
            raise HTTPException(status_code=409, detail="Decision is not writable")
        wording = record(connection, "document", "policy-wording", PolicyWording)
        sections = {
            int(number) for number in re.findall(r"^## (\d+)\.", wording.content, re.M)
        }
        if not set(decision.policy_sections) <= sections:
            raise HTTPException(status_code=422, detail="Unknown policy section")
        company = record(connection, "company", "undercover", Company)
        status: QueueStatus = "decided"
        if (
            decision.outcome == "approve"
            and decision.payout > company.payout_approval_limit
        ):
            status = "waiting_for_sign_off"
        saved = Decision(**decision.model_dump(), recorded_at=timestamp())
        connection.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?)",
            (
                claim_id,
                decision.thread_id,
                saved.model_dump_json(),
                cents(saved.payout),
            ),
        )
        connection.execute(
            "UPDATE claims SET status = ? WHERE claim_id = ?", (status, claim_id)
        )
    return DecisionResult(claim_id=claim_id, status=status, decision=saved)


def sign_off(database: Database, claim_id: str, handler_id: str) -> SignOffResult:
    with database.write() as connection:
        claim = claim_row(connection, claim_id)
        handler = record(connection, "handler", handler_id, Handler)
        if not handler.can_approve_over_limit:
            raise HTTPException(
                status_code=403, detail="Handler cannot approve over limit"
            )
        if claim["status"] != "waiting_for_sign_off":
            raise HTTPException(status_code=409, detail="Claim does not need sign-off")
        approval = SignOff(handler_id=handler.handler_id, signed_off_at=timestamp())
        connection.execute(
            "INSERT INTO sign_offs VALUES (?, ?, ?)",
            (claim_id, handler_id, approval.signed_off_at),
        )
        connection.execute(
            "UPDATE claims SET status = 'decided' WHERE claim_id = ?", (claim_id,)
        )
        decision = stored_decision(connection, claim_id)
        if decision is None:
            raise HTTPException(status_code=409, detail="No decision to sign off")
        append_event(
            connection,
            claim_id,
            ActivityInput(
                thread_id=decision.thread_id,
                kind="sign_off",
                message=f"Handler {handler_id} signed off the approval.",
            ),
        )
    return SignOffResult(claim_id=claim_id, sign_off=approval)


def pay(database: Database, claim_id: str, request: PaymentInput) -> PaymentResult:
    with database.write() as connection:
        claim = claim_row(connection, claim_id)
        decision = stored_decision(connection, claim_id)
        if (
            decision is None
            or decision.outcome != "approve"
            or decision.payout == 0
            or claim["status"] in {"waiting", "in_progress"}
        ):
            raise HTTPException(status_code=409, detail="No approved payment is due")
        if request.amount != decision.payout:
            raise HTTPException(
                status_code=409, detail="Amount does not match approval"
            )
        if stored_payment(connection, claim_id):
            raise HTTPException(status_code=409, detail="Claim already paid")
        company = record(connection, "company", "undercover", Company)
        if (
            decision.payout > company.payout_approval_limit
            and stored_sign_off(connection, claim_id) is None
        ):
            raise HTTPException(status_code=409, detail="Handler sign-off required")
        payment = Payment(amount=decision.payout, paid_at=timestamp())
        connection.execute(
            "INSERT INTO payments VALUES (?, ?, ?)",
            (claim_id, cents(payment.amount), payment.paid_at),
        )
        append_event(
            connection,
            claim_id,
            ActivityInput(
                thread_id=decision.thread_id,
                kind="payment",
                message=f"Simulated payment recorded: ${payment.amount:,.2f}.",
            ),
        )
    return PaymentResult(claim_id=claim_id, payment=payment)
