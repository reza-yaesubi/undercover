"""Read the claim workspace from the backend's records."""

from backend import workflow
from backend.database import Database, claim_row, record
from backend.instructions import agent_instructions
from backend.models import (
    Claim,
    ClaimDetail,
    ClaimQueue,
    ClaimSummary,
    Company,
    Customer,
    Handler,
    HandlerList,
    Instructions,
    Plan,
    Policy,
    PolicyWording,
)


def list_claims(database: Database) -> ClaimQueue:
    with database.connect() as connection:
        rows = connection.execute("SELECT * FROM claims ORDER BY claim_id").fetchall()
        summaries = []
        for row in rows:
            claim = Claim.model_validate_json(row["body"])
            customer = record(connection, "customer", claim.customer_id, Customer)
            summaries.append(
                ClaimSummary(
                    claim_id=claim.claim_id,
                    customer_name=customer.name,
                    claim_type=claim.claim_type,
                    summary=claim.summary,
                    amount_claimed=claim.amount_claimed,
                    status=row["status"],
                )
            )
    return ClaimQueue(claims=summaries, total=len(summaries))


def get_claim(database: Database, claim_id: str) -> ClaimDetail:
    with database.connect() as connection:
        row = claim_row(connection, claim_id)
        claim = Claim.model_validate_json(row["body"]).model_copy(
            update={"status": row["status"]}
        )
        policy = record(connection, "policy", claim.policy_id, Policy)
        customer = record(connection, "customer", claim.customer_id, Customer)
        plan = record(connection, "plan", policy.plan, Plan)
        decision = workflow.stored_decision(connection, claim_id)
        sign_off = workflow.stored_sign_off(connection, claim_id)
        payment = workflow.stored_payment(connection, claim_id)
        run = workflow.latest_run(connection, claim_id)
    return ClaimDetail(
        claim=claim,
        policy=policy,
        customer=customer,
        plan=plan.model_copy(
            update={
                "add_ons": [
                    addon for addon in plan.add_ons if addon.add_on in policy.add_ons
                ]
            }
        ),
        decision=decision,
        sign_off=sign_off,
        payment=payment,
        run=run,
    )


def get_wording(database: Database) -> PolicyWording:
    with database.connect() as connection:
        return record(connection, "document", "policy-wording", PolicyWording)


def get_instructions(database: Database) -> Instructions:
    with database.connect() as connection:
        company = record(connection, "company", "undercover", Company)
    return agent_instructions(company)


def list_handlers(database: Database) -> HandlerList:
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT body FROM records WHERE kind = 'handler' ORDER BY record_id"
        ).fetchall()
    return HandlerList(
        handlers=[Handler.model_validate_json(row["body"]) for row in rows]
    )
