"""Bounded session-only maintenance; run daily using the restricted application role."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import database_engine
from app.models import SessionRecord


def cleanup_sessions(
    engine: Engine | Connection, now: datetime, batch_size: int = 500, batches: int = 10
) -> int:
    if not 1 <= batch_size <= 500 or not 1 <= batches <= 10:
        raise ValueError("Cleanup bounds exceeded")
    total = 0
    for _ in range(batches):
        with Session(engine) as db, db.begin():
            ids = list(
                db.scalars(
                    select(SessionRecord.id)
                    .where(
                        or_(
                            SessionRecord.expires_at <= now,
                            SessionRecord.revoked_at <= now - timedelta(days=1),
                        )
                    )
                    .order_by(SessionRecord.expires_at)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            )
            if ids:
                db.execute(delete(SessionRecord).where(SessionRecord.id.in_(ids)))
            total += len(ids)
        if len(ids) < batch_size:
            break
    return total


def main() -> None:
    engine = database_engine(get_settings().database_url)
    try:
        print(f"Expired/revoked sessions removed: {cleanup_sessions(engine, datetime.now(UTC))}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
