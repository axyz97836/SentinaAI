from collections.abc import Callable, Iterator
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.errors import AuthError
from app.auth.service import AuthService, Principal, Role
from app.models import (
    Alert,
    Case,
    Dataset,
    Job,
    Membership,
    ModelVersion,
    Organization,
    Transaction,
    User,
)


def service(request: Request) -> AuthService:
    return cast(AuthService, request.app.state.auth)


def database(request: Request) -> Iterator[Session]:
    # Function scope commits before sending cookies/HTTP success, including audit.
    with service(request).sessions.begin() as db:
        yield db


Database = Annotated[Session, Depends(database, scope="function")]


def validate_origin(request: Request, *, required: bool = True) -> None:
    origin = request.headers.get("origin")
    if (
        (required and origin is None)
        or (origin is not None and origin not in service(request).settings.allowed_origins)
        or request.headers.get("sec-fetch-site") == "cross-site"
    ):
        raise AuthError(403, "CSRF_REJECTED", "Request origin or CSRF token is invalid.")


def validate_csrf(request: Request, *, login: bool = False) -> None:
    auth = service(request)
    validate_origin(request)
    token = request.cookies.get(auth.settings.session_cookie, "")
    if login and not token:
        token = request.cookies.get(auth.settings.preauth_cookie, "")
        if not auth.csrf.valid_preauth(token, int(auth.clock().timestamp())):
            raise AuthError(403, "CSRF_REJECTED", "Request origin or CSRF token is invalid.")
        purpose = "preauth-header"
    else:
        purpose = "session-header"
    if not token or not auth.csrf.matches(
        request.headers.get("x-csrf-token", ""), auth.csrf.proof(purpose, token)
    ):
        raise AuthError(403, "CSRF_REJECTED", "Request origin or CSRF token is invalid.")


def authenticated(request: Request, db: Database) -> Principal:
    auth = service(request)
    raw = request.cookies.get(auth.settings.session_cookie, "")
    # Authenticate first for correct 401 semantics, but no last-seen write until CSRF passes.
    auth.resolve(db, raw, touch=False)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        validate_csrf(request)
    return auth.resolve(db, raw)


Identity = Annotated[Principal, Depends(authenticated)]


def require_roles(*roles: Role) -> Callable[..., Principal]:
    def authorized(principal: Identity) -> Principal:
        if principal.role not in roles:
            raise AuthError(403, "FORBIDDEN", "You do not have permission for this operation.")
        return principal

    return authorized


def organization_record[T: Transaction | Job | Alert | Case | Dataset | ModelVersion](
    db: Session, model: type[T], identifier: UUID, principal: Principal
) -> T:
    record = db.scalar(
        select(model).where(
            model.id == identifier,
            model.organization_id == principal.organization_id,
        )
    )
    if record is None:
        raise AuthError(404, "NOT_FOUND", "Record is not available.")
    return record


def guard_admin_removal(db: Session, organization_id: UUID, user_id: UUID) -> None:
    """Future management services must hold this org lock through their mutation.

    This is an invariant guard, not authorization: call only after ADMIN and tenant
    checks. Every future admin removal/deactivation must use the same lock order.
    """
    db.execute(
        select(Organization.id).where(Organization.id == organization_id).with_for_update()
    ).one()
    admins = list(
        db.scalars(
            select(User.id)
            .join(Membership)
            .where(
                Membership.organization_id == organization_id,
                Membership.role == "ADMIN",
                User.is_active.is_(True),
            )
        )
    )
    if user_id in admins and len(admins) == 1:
        raise AuthError(409, "LAST_ADMIN", "The last active administrator must be preserved.")
