"""Load only the business records permitted for the pilot."""

from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from backend.models import Claim, Company, Customer, Handler, PlanCatalog, Policy

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class SeedData(BaseModel):
    claims: list[Claim]
    policies: list[Policy]
    customers: list[Customer]
    plans: PlanCatalog
    handlers: list[Handler]
    company: Company
    wording: str


def load_seed(directory: Path = DATA_DIR) -> SeedData:
    """Read the explicit pilot allowlist, never evaluation or manual files."""
    return SeedData(
        claims=TypeAdapter(list[Claim]).validate_json(
            (directory / "claims.json").read_text(encoding="utf-8")
        ),
        policies=TypeAdapter(list[Policy]).validate_json(
            (directory / "policies.json").read_text(encoding="utf-8")
        ),
        customers=TypeAdapter(list[Customer]).validate_json(
            (directory / "customers.json").read_text(encoding="utf-8")
        ),
        plans=PlanCatalog.model_validate_json(
            (directory / "plans.json").read_text(encoding="utf-8")
        ),
        handlers=TypeAdapter(list[Handler]).validate_json(
            (directory / "handlers.json").read_text(encoding="utf-8")
        ),
        company=Company.model_validate_json(
            (directory / "company.json").read_text(encoding="utf-8")
        ),
        wording=(directory / "policy_wording.md").read_text(encoding="utf-8"),
    )
