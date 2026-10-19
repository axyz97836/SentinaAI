"""Alembic uses the dedicated migration identity, never application credentials."""

from alembic import context
from sqlalchemy import text

from app import models  # noqa: F401 -- register every mapped table
from app.database import Base, MigrationSettings, database_engine

settings = MigrationSettings()

if context.is_offline_mode():
    context.configure(
        dialect_name="postgresql",
        target_metadata=Base.metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = database_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
                compare_type=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                connection.execute(text("SET LOCAL search_path = public"))
                context.run_migrations()
    finally:
        engine.dispose()
