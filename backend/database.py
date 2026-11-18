"""SQLite storage with short-lived connections and non-destructive seeding."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

from backend.models import PolicyWording
from backend.seed import SeedData

DEFAULT_DATABASE = Path(__file__).resolve().parents[1] / "undercover.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    kind TEXT NOT NULL,
    record_id TEXT NOT NULL,
    body TEXT NOT NULL,
    PRIMARY KEY (kind, record_id)
);
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('waiting', 'in_progress', 'waiting_for_sign_off', 'decided')
    )
);
"""


@dataclass(frozen=True)
class Database:
    path: Path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path, timeout=10)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection

    def initialize(self, seed: SeedData) -> None:
        """Create missing tables and insert seed records without resetting work."""
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            for kind, identifier, record in seed_records(seed):
                connection.execute(
                    "INSERT OR IGNORE INTO records VALUES (?, ?, ?)",
                    (kind, identifier, record.model_dump_json()),
                )
            for claim in seed.claims:
                connection.execute(
                    "INSERT OR IGNORE INTO claims VALUES (?, ?, ?)",
                    (claim.claim_id, claim.model_dump_json(), claim.status),
                )


def seed_records(seed: SeedData) -> Iterator[tuple[str, str, BaseModel]]:
    for policy in seed.policies:
        yield "policy", policy.policy_id, policy
    for customer in seed.customers:
        yield "customer", customer.customer_id, customer
    for handler in seed.handlers:
        yield "handler", handler.handler_id, handler
    for plan in seed.plans.plans:
        yield (
            "plan",
            plan.plan,
            plan.model_copy(
                update={
                    "add_ons": seed.plans.add_ons,
                    "deductible_applies_to": seed.plans.deductible_applies_to,
                }
            ),
        )
    yield "company", "undercover", seed.company
    yield (
        "document",
        "policy-wording",
        PolicyWording(
            version=seed.company.policy_wording_version, content=seed.wording
        ),
    )


def claim_row(connection: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return row


def record[T: BaseModel](
    connection: sqlite3.Connection, kind: str, identifier: str, model: type[T]
) -> T:
    row = connection.execute(
        "SELECT body FROM records WHERE kind = ? AND record_id = ?", (kind, identifier)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{kind.capitalize()} not found")
    return model.model_validate_json(row["body"])
