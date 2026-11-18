"""Synthetic workflow cases derived from the policy, not evaluation answers."""

from dataclasses import dataclass

from backend.models import ClaimItem, Document
from backend.seed import SeedData, load_seed
from backend.workflow_models import DecisionDraft, Outcome


@dataclass(frozen=True)
class Scenario:
    claim_type: str
    plan: str
    amount: float
    summary: str
    outcome: Outcome
    payout: str
    sections: list[int]
    explanation: list[str]
    calculation: str


SCENARIOS = {
    "CLM-T420": Scenario(
        claim_type="trip_delay",
        plan="premium",
        amount=420,
        summary="Crew delay of 19 hours and 15 minutes",
        outcome="approve",
        payout="420.00",
        sections=[3, 10],
        explanation=[
            "The documented crew delay meets the Premium waiting period in section 3.",
            "The $420.00 of receipts is below the $800.00 limit, with no deductible.",
        ],
        calculation="245.00 + 95.00 + 80.00 = 420.00; no deductible.",
    ),
    "CLM-TBAG": Scenario(
        claim_type="baggage",
        plan="premium",
        amount=500,
        summary="Reported carrier loss with $50 compensation",
        outcome="approve",
        payout="200.00",
        sections=[1, 5, 10],
        explanation=[
            "The reported baggage loss is covered under section 5.",
            "The item cap, compensation and deductible reduce the payout to $200.00.",
        ],
        calculation="min(500.00, 300.00) - 50.00 - 50.00 = 200.00.",
    ),
    "CLM-T1000": Scenario(
        claim_type="emergency_medical",
        plan="first",
        amount=1000,
        summary="Documented emergency medical treatment",
        outcome="approve",
        payout="1000.00",
        sections=[7, 10],
        explanation=[
            "The sudden illness and necessary treatment are covered under section 7.",
            "The First plan has no deductible, so the eligible bill pays $1,000.00.",
        ],
        calculation="1000.00 - 0.00 = 1000.00; below the medical maximum.",
    ),
    "CLM-T100001": Scenario(
        claim_type="emergency_medical",
        plan="first",
        amount=1000.01,
        summary="Emergency medical approval needing sign-off",
        outcome="approve",
        payout="1000.01",
        sections=[7, 10],
        explanation=[
            "The documented sudden illness is covered under section 7.",
            "The $1,000.01 First-plan payout awaits handler sign-off.",
        ],
        calculation="1000.01 - 0.00 = 1000.01; below the medical maximum.",
    ),
    "CLM-TDECLINE": Scenario(
        claim_type="baggage_delay",
        plan="premium",
        amount=100,
        summary="Baggage delay on the journey home",
        outcome="decline",
        payout="0.00",
        sections=[4],
        explanation=[
            "Section 4 excludes baggage delays on the journey home.",
            "No payout is due for the submitted expenses.",
        ],
        calculation="Journey-home exclusion: 0.00 payable.",
    ),
    "CLM-TREFER": Scenario(
        claim_type="emergency_medical",
        plan="first",
        amount=250,
        summary="Medical records missing from the claim",
        outcome="refer",
        payout="0.00",
        sections=[7, 11],
        explanation=[
            "Section 7 requires medical records as well as an itemized bill.",
            "Refer for the missing records under section 11 before deciding coverage.",
        ],
        calculation="Evidence incomplete: 0.00 payable pending review.",
    ),
}


def draft_for(claim_id: str) -> DecisionDraft:
    scenario = SCENARIOS[claim_id]
    return DecisionDraft.model_validate(
        {
            "outcome": scenario.outcome,
            "payout": scenario.payout,
            "reason": scenario.explanation,
            "policy_sections": scenario.sections,
            "calculation": scenario.calculation,
        }
    )


def evidence_for(claim_id: str) -> tuple[list[ClaimItem], list[Document]]:
    scenario = SCENARIOS[claim_id]
    if claim_id == "CLM-T420":
        items = [
            ClaimItem(description="Hotel", category="accommodation", amount=245),
            ClaimItem(description="Meals", category="meals", amount=95),
            ClaimItem(description="Taxis", category="transport", amount=80),
        ]
        documents = [
            Document(
                name="Carrier report",
                type="carrier_report",
                content=(
                    "Crew delay: June 18, 2026 11:40 departure canceled; "
                    "actual departure June 19, 2026 06:55."
                ),
            ),
            *[
                Document(
                    name=f"{item.description} receipt",
                    type="receipt",
                    content=f"Paid ${item.amount:.2f} during the covered delay.",
                )
                for item in items
            ],
        ]
        return items, documents
    items = [
        ClaimItem(
            description=scenario.summary,
            category=scenario.claim_type,
            amount=scenario.amount,
        )
    ]
    documents = [
        Document(
            name="Itemized receipt",
            type="receipt",
            content=f"Paid ${scenario.amount:.2f} on June 18, 2026.",
        )
    ]
    if scenario.claim_type == "emergency_medical" and claim_id != "CLM-TREFER":
        documents.append(
            Document(
                name="Medical records",
                type="medical_record",
                content=(
                    "Sudden appendicitis on June 18, 2026; urgent treatment necessary. "
                    "No prior symptoms, treatment, medication changes or sports."
                ),
            )
        )
    if scenario.claim_type in {"baggage", "baggage_delay"}:
        documents.append(
            Document(
                name="Carrier report",
                type="carrier_report",
                content=(
                    "Carrier confirmed a reported lost item and paid $50 compensation."
                    if claim_id == "CLM-TBAG"
                    else "Checked bag delivered 30 hours late on the journey home."
                ),
            )
        )
    return items, documents


def pilot_seed() -> SeedData:
    seed = load_seed()
    customer = seed.customers[0].model_copy(
        update={
            "customer_id": "CUS-TEST",
            "name": "Pilot Test Traveler",
            "previous_claims": [],
        }
    )
    claims = []
    policies = []
    for claim_id, scenario in SCENARIOS.items():
        items, documents = evidence_for(claim_id)
        policy_id = f"POL-{claim_id}"
        policies.append(
            seed.policies[0].model_copy(
                update={
                    "policy_id": policy_id,
                    "customer_id": customer.customer_id,
                    "plan": scenario.plan,
                    "travelers": [customer.name],
                    "add_ons": [],
                }
            )
        )
        claims.append(
            seed.claims[0].model_copy(
                update={
                    "claim_id": claim_id,
                    "policy_id": policy_id,
                    "customer_id": customer.customer_id,
                    "claim_type": scenario.claim_type,
                    "summary": scenario.summary,
                    "story": (
                        f"{scenario.summary}. "
                        "The submitted documents describe my claim."
                    ),
                    "items": items,
                    "documents": documents,
                    "amount_claimed": scenario.amount,
                    "status": "waiting",
                }
            )
        )
    return seed.model_copy(
        update={"claims": claims, "policies": policies, "customers": [customer]}
    )
