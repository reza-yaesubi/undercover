"""Required workflow inputs and persisted workflow responses."""

from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

QueueStatus = Literal["waiting", "in_progress", "waiting_for_sign_off", "decided"]
Outcome = Literal["approve", "decline", "refer"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=14, decimal_places=2),
    PlainSerializer(lambda value: f"{value:.2f}", return_type=str),
]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DecisionDraft(RequestModel):
    outcome: Outcome
    payout: Money
    reason: Annotated[list[Text], Field(min_length=2, max_length=3)]
    policy_sections: Annotated[list[Annotated[int, Field(ge=1)]], Field(min_length=1)]
    calculation: Text

    @model_validator(mode="after")
    def check_non_approval_payout(self) -> Self:
        if self.outcome != "approve" and self.payout != 0:
            raise ValueError("Declined and referred claims must have a zero payout")
        return self


class DecisionInput(DecisionDraft):
    thread_id: Text


class Decision(DecisionInput):
    recorded_at: str


class SignOffInput(RequestModel):
    handler_id: Text


class SignOff(BaseModel):
    handler_id: str
    signed_off_at: str


class PaymentInput(RequestModel):
    amount: Money


class Payment(BaseModel):
    amount: Money
    simulated: Literal[True] = True
    paid_at: str


class Run(BaseModel):
    thread_id: str
    status: Literal["running", "completed", "failed"]
    started_at: str
    finished_at: str | None
    error: str | None


class RunStart(BaseModel):
    claim_id: str
    thread_id: str
    status: Literal["in_progress"] = "in_progress"


class DecisionResult(BaseModel):
    claim_id: str
    status: QueueStatus
    decision: Decision


class SignOffResult(BaseModel):
    claim_id: str
    status: Literal["decided"] = "decided"
    sign_off: SignOff


class PaymentResult(BaseModel):
    claim_id: str
    payment: Payment


ActivityKind = Literal[
    "started", "tool_call", "tool_result", "completed", "error", "sign_off", "payment"
]


class ActivityInput(RequestModel):
    thread_id: Text
    kind: ActivityKind
    message: Text


class Activity(ActivityInput):
    sequence: int
    created_at: str


class ActivityList(BaseModel):
    events: list[Activity]


def cents(amount: Decimal) -> int:
    return int(amount * 100)
