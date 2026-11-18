"""The pilot's business records and read responses."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

QueueStatus = Literal["waiting", "in_progress", "waiting_for_sign_off", "decided"]


class ClaimItem(BaseModel):
    description: str
    category: str
    amount: float


class Document(BaseModel):
    name: str
    type: str
    content: str


class Claim(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    claim_type: str
    submitted_on: str
    incident_date: str
    incident_location: str
    summary: str
    story: str
    items: list[ClaimItem]
    amount_claimed: float
    documents: list[Document]
    status: QueueStatus

    @field_validator("status", mode="before")
    @classmethod
    def normalize_seed_status(cls, value: str) -> str:
        return "waiting" if value == "open" else value


class Trip(BaseModel):
    destination: str
    departs_on: str
    returns_on: str
    trip_cost: float


class Policy(BaseModel):
    policy_id: str
    customer_id: str
    plan: str
    add_ons: list[str]
    purchased_on: str
    sold_through: str
    trip: Trip
    travelers: list[str]
    status: str


class PreviousClaim(BaseModel):
    claim_id: str
    filed_on: str
    incident_date: str
    claim_type: str
    summary: str
    outcome: str
    amount_paid: float


class Address(BaseModel):
    street: str
    city: str
    state: str
    zip: str


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: str
    date_of_birth: str
    address: Address
    customer_since: str
    previous_claims: list[PreviousClaim]


class AddOn(BaseModel):
    add_on: str
    name: str
    effect: str
    electronics_per_item_limit: float | None = None


class Plan(BaseModel):
    plan: str
    name: str
    trip_cancellation_max: float
    trip_delay_waiting_hours: float
    trip_delay_max: float
    baggage_delay_waiting_hours: float
    baggage_delay_max: float
    baggage_max: float
    per_item_limit: float
    passport_max: float
    emergency_medical_max: float
    deductible: float
    deductible_applies_to: list[str] = Field(default_factory=list)
    add_ons: list[AddOn] = Field(default_factory=list)


class PlanCatalog(BaseModel):
    plans: list[Plan]
    deductible_applies_to: list[str]
    add_ons: list[AddOn]


class Handler(BaseModel):
    handler_id: str
    name: str
    can_approve_over_limit: bool


class Company(BaseModel):
    currency: Literal["USD"]
    payout_approval_limit: Decimal = Field(ge=0, decimal_places=2)
    policy_wording_version: str


class PolicyWording(BaseModel):
    version: str
    content: str


class Instructions(BaseModel):
    content: str
    currency: Literal["USD"]
    payout_approval_limit: str


class ClaimSummary(BaseModel):
    claim_id: str
    customer_name: str
    claim_type: str
    summary: str
    amount_claimed: float
    status: QueueStatus


class ClaimQueue(BaseModel):
    claims: list[ClaimSummary]
    total: int


class ClaimDetail(BaseModel):
    claim: Claim
    policy: Policy
    customer: Customer
    plan: Plan
    decision: None = None
    sign_off: None = None
    payment: None = None
    run: None = None


class HandlerList(BaseModel):
    handlers: list[Handler]
