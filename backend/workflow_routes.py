"""The decision and payment operations shared by handlers and agent tools."""

from fastapi import FastAPI

from backend import workflow
from backend.database import Database
from backend.workflow_models import (
    DecisionInput,
    DecisionResult,
    PaymentInput,
    PaymentResult,
    SignOffInput,
    SignOffResult,
)


def add_workflow_routes(app: FastAPI, database: Database) -> None:
    @app.post(
        "/api/claims/{claim_id}/decision",
        operation_id="record_decision",
        status_code=201,
    )
    def record_decision(claim_id: str, decision: DecisionInput) -> DecisionResult:
        """Store the active run's decision without replacing an earlier decision."""
        return workflow.record_decision(database, claim_id, decision)

    @app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
    def sign_off_claim(claim_id: str, approval: SignOffInput) -> SignOffResult:
        """Record a handler's sign-off without making a payment."""
        return workflow.sign_off(database, claim_id, approval.handler_id)

    @app.post("/api/claims/{claim_id}/pay", operation_id="pay_claim", status_code=201)
    def pay_claim(claim_id: str, payment: PaymentInput) -> PaymentResult:
        """Record the exact approved amount as a guarded simulated payment."""
        return workflow.pay(database, claim_id, payment)
