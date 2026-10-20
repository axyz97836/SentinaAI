from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth.crypto import CSRF, new_token, token_hash
from app.auth.errors import AuthError, unauthorized
from app.auth.limiter import LoginLimiter
from app.config import Settings
from app.database import database_engine
from app.models import AuditLog, Membership, Organization, SessionRecord, User

Role = Literal["ANALYST", "RISK_MANAGER", "ADMIN"]
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, type=Type.ID)


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    organization_id: UUID
    membership_id: UUID
    session_id: UUID
    role: Role
    email: str
    display_name: str
    organization_name: str


class AuthService:
    def __init__(
        self,
        settings: Settings,
        engine: Engine | None = None,
        limiter: LoginLimiter | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not settings.auth_secret:
            raise ValueError("AUTH_SECRET is required by the API")
        self.settings = settings
        self.engine = engine or database_engine(settings.database_url)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.csrf = CSRF(settings.auth_secret.get_secret_value())
        self.limiter = limiter or LoginLimiter(settings, self.csrf)
        self.clock = clock
        # Same Argon2id work for an unknown account; never a reusable credential.
        self.dummy_hash = HASHER.hash(new_token())

    def close(self) -> None:
        self.limiter.close()
        self.engine.dispose()

    def principal(self, db: Session, record: SessionRecord) -> Principal:
        user = db.get(User, record.user_id)
        memberships = db.execute(
            select(Membership, Organization)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(Membership.user_id == record.user_id)
            .limit(2)
        ).all()
        # The approved session schema has no tenant selection. Never guess or
        # accept a client-supplied organization if membership is ambiguous.
        if not user or not user.is_active or len(memberships) != 1:
            raise unauthorized()
        membership, organization = memberships[0]
        return Principal(
            user.id,
            organization.id,
            membership.id,
            record.id,
            cast(Role, membership.role),
            user.email,
            user.display_name,
            organization.name,
        )

    def resolve(self, db: Session, raw_token: str, *, touch: bool = True) -> Principal:
        digest = token_hash(raw_token)
        if digest is None:
            raise unauthorized()
        record = db.scalar(
            select(SessionRecord).where(SessionRecord.token_hash == digest).with_for_update()
        )
        now = self.clock()
        if (
            record is None
            or record.revoked_at is not None
            or record.expires_at <= now
            or (record.last_seen_at or record.created_at)
            <= now - timedelta(seconds=self.settings.auth_idle_seconds)
        ):
            raise unauthorized()
        principal = self.principal(db, record)
        if touch:
            record.last_seen_at = now
        return principal

    def login(
        self, db: Session, email: str, password: str, old_token: str, request_id: str
    ) -> tuple[Principal, str]:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        encoded = user.password_hash if user else self.dummy_hash
        try:
            valid = encoded.startswith("$argon2id$") and HASHER.verify(encoded, password)
        except (VerificationError, InvalidHashError):
            valid = False
        if not valid or user is None or not user.is_active:
            raise AuthError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
        now = self.clock()
        raw = new_token()
        record = SessionRecord(
            user_id=user.id,
            token_hash=token_hash(raw),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=self.settings.auth_session_seconds),
        )
        db.add(record)
        db.flush()
        try:
            principal = self.principal(db, record)
        except AuthError:
            raise AuthError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.") from None
        old_digest = token_hash(old_token)
        if old_digest:
            db.execute(
                update(SessionRecord)
                .where(SessionRecord.token_hash == old_digest, SessionRecord.revoked_at.is_(None))
                .values(revoked_at=now)
            )
        self.audit(db, principal, "AUTH_LOGIN", request_id)
        return principal, raw

    def logout(self, db: Session, principal: Principal, request_id: str) -> None:
        db.execute(
            update(SessionRecord)
            .where(SessionRecord.id == principal.session_id)
            .values(revoked_at=self.clock())
        )
        self.audit(db, principal, "AUTH_LOGOUT", request_id)

    @staticmethod
    def audit(db: Session, principal: Principal, action: str, request_id: str) -> None:
        db.add(
            AuditLog(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                action=action,
                resource_type="SESSION",
                resource_id=principal.session_id,
                metadata_json={},
                request_id=request_id,
            )
        )
        db.flush()
