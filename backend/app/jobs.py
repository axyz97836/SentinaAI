"""A dedicated connection holds the job lock across durable progress commits."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


@contextmanager
def job_session(engine: Engine, job_id: UUID) -> Iterator[Session | None]:
    lock = int.from_bytes(job_id.bytes[:8], "big", signed=True)
    with engine.connect() as connection:
        acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock})
        connection.commit()
        if not acquired:
            yield None
            return
        try:
            with Session(connection, expire_on_commit=False) as db:
                yield db
        finally:
            try:
                if not connection.invalidated:
                    connection.rollback()
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock})
                    connection.commit()
            except SQLAlchemyError:
                connection.invalidate()
