"""Writing to the activity log. Append-only."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ActivityLog


def log(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    entity: str,
    entity_id: object = None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(ActivityLog(
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=None if entity_id is None else str(entity_id),
        before=before,
        after=after,
    ))
