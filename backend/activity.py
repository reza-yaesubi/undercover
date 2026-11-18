"""Persist operational steps without recording hidden reasoning or credentials."""

import sqlite3

from fastapi import HTTPException

from backend.database import Database, claim_row, timestamp
from backend.workflow_models import Activity, ActivityInput, ActivityList


def append_event(
    connection: sqlite3.Connection, claim_id: str, event: ActivityInput
) -> Activity:
    created_at = timestamp()
    row = connection.execute(
        """INSERT INTO activity (claim_id, thread_id, kind, message, created_at)
           VALUES (?, ?, ?, ?, ?) RETURNING sequence""",
        (claim_id, event.thread_id, event.kind, event.message, created_at),
    ).fetchone()
    return Activity(
        **event.model_dump(), sequence=row["sequence"], created_at=created_at
    )


def record_activity(
    database: Database, claim_id: str, event: ActivityInput
) -> Activity:
    with database.write() as connection:
        claim_row(connection, claim_id)
        run = connection.execute(
            "SELECT * FROM runs WHERE claim_id = ? ORDER BY run_id DESC LIMIT 1",
            (claim_id,),
        ).fetchone()
        if (
            run is None
            or run["thread_id"] != event.thread_id
            or run["status"] != "running"
        ):
            raise HTTPException(status_code=409, detail="Run is not active")
        return append_event(connection, claim_id, event)


def list_activity(database: Database, claim_id: str) -> ActivityList:
    with database.connect() as connection:
        claim_row(connection, claim_id)
        rows = connection.execute(
            """SELECT thread_id, kind, message, sequence, created_at
               FROM activity WHERE claim_id = ? ORDER BY sequence""",
            (claim_id,),
        ).fetchall()
    return ActivityList(events=[Activity.model_validate(dict(row)) for row in rows])
