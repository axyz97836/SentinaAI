"""Explicit local-only provisioning; never creates transactions or authentication endpoints."""

import argparse
import json
import os
import secrets
import stat
import sys
from pathlib import Path

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import database_engine
from app.models import Membership, Organization, RiskSettings, User

ORGANIZATION_NAME = "SentinelAI Fictional Demo"
DEMO_ACCOUNTS = (
    ("admin@sentinel-demo.invalid", "Demo Administrator", "ADMIN"),
    ("risk-manager@sentinel-demo.invalid", "Demo Risk Manager", "RISK_MANAGER"),
    ("analyst@sentinel-demo.invalid", "Demo Analyst", "ANALYST"),
)
HASHER = PasswordHasher(type=Type.ID, time_cost=3, memory_cost=65536, parallelism=4)


def _credentials(path: Path, accounts_exist: bool) -> dict[str, str]:
    expected = {email for email, _, _ in DEMO_ACCOUNTS}
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        if accounts_exist:
            raise ValueError(
                "Demo accounts exist but the credential file is missing; restore it."
            ) from None
        credentials = {email: secrets.token_urlsafe(32) for email in expected}
        # File creation is inside the database advisory lock. Never overwrite or rotate.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump({"purpose": "LOCAL_SYNTHETIC_DEMO_ONLY", "accounts": credentials}, output)
            output.flush()
            os.fsync(output.fileno())
        return credentials
    with os.fdopen(fd, "r") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError("Demo credential file must be a regular file with mode 0600.")
        values = json.load(source)
    if not isinstance(values, dict) or values.get("purpose") != "LOCAL_SYNTHETIC_DEMO_ONLY":
        raise ValueError("Invalid demo credential file; preserved without changes.")
    accounts = values.get("accounts")
    if not isinstance(accounts, dict) or set(accounts) != expected:
        raise ValueError("Invalid demo accounts in credential file; preserved without changes.")
    if any(not isinstance(value, str) or len(value) < 43 for value in accounts.values()):
        raise ValueError("Invalid demo credential format; preserved without changes.")
    return {str(key): str(value) for key, value in accounts.items()}


def seed_demo(engine: Engine, credentials_file: Path, environment: str) -> None:
    if environment != "local":
        raise ValueError("Demo seed is permitted only in an explicitly local environment.")
    with Session(engine) as session, session.begin():
        # Serialize repeated/concurrent seeds without adding a domain table or unique name.
        session.execute(text("SELECT pg_advisory_xact_lock(53414902)"))
        emails = [email for email, _, _ in DEMO_ACCOUNTS]
        users = {
            user.email.lower(): user
            for user in session.scalars(select(User).where(func.lower(User.email).in_(emails)))
        }
        credentials = _credentials(credentials_file, bool(users))
        organization = session.scalar(
            select(Organization).where(Organization.name == ORGANIZATION_NAME)
        )
        count = session.scalar(
            select(func.count())
            .select_from(Organization)
            .where(Organization.name == ORGANIZATION_NAME)
        )
        if count and count > 1:
            raise ValueError("Multiple demo organizations found; refusing to guess.")
        if organization is None:
            organization = Organization(name=ORGANIZATION_NAME)
            session.add(organization)
            session.flush()
        admin: User | None = None
        for email, display_name, role in DEMO_ACCOUNTS:
            user = users.get(email)
            if user is None:
                user = User(
                    email=email,
                    display_name=display_name,
                    password_hash=HASHER.hash(credentials[email]),
                )
                session.add(user)
                session.flush()
            else:
                try:
                    HASHER.verify(user.password_hash, credentials[email])
                except VerificationError:
                    raise ValueError(
                        "Existing demo password differs; no credentials were rotated."
                    ) from None
                if not user.is_active:
                    raise ValueError(
                        "Existing demo account is inactive; refusing to reactivate it."
                    )
            membership = session.scalar(
                select(Membership).where(
                    Membership.organization_id == organization.id, Membership.user_id == user.id
                )
            )
            if membership is None:
                session.add(Membership(organization_id=organization.id, user_id=user.id, role=role))
            elif membership.role != role:
                raise ValueError("Existing demo role differs; refusing to overwrite it.")
            if role == "ADMIN":
                admin = user
        if admin is None:
            raise RuntimeError("Demo ADMIN was not provisioned")
        if session.get(RiskSettings, organization.id) is None:
            session.add(RiskSettings(organization_id=organization.id, updated_by=admin.id))
        # Rule parameters are not specified completely in the approved docs; seed none.


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed fictional local demo accounts only.")
    parser.add_argument("--credentials-file", type=Path, default=Path("/run/demo/credentials.json"))
    args = parser.parse_args()
    engine: Engine | None = None
    try:
        # Refuse before loading settings, connecting, writing a file or creating a hash.
        if os.environ.get("APP_ENV") != "local":
            raise ValueError("Demo seed requires APP_ENV=local")
        settings = get_settings()
        engine = database_engine(settings.database_url)
        seed_demo(engine, args.credentials_file, settings.app_env)
    except Exception:
        print(
            "Demo seed refused or failed. Verify local configuration and the credential file; "
            "no existing passwords were rotated.",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    print(
        "Verified fictional demo organization, three role accounts/memberships and risk settings. "
        "Credentials remain only in the protected local file."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
