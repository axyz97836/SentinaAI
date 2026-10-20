"""PYTEST_DONT_REWRITE: keep temporary credential values out of assertion diagnostics."""

import hmac
import logging
import secrets
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker

from app.auth.cleanup import cleanup_sessions
from app.auth.crypto import new_token, token_hash
from app.auth.dependencies import (
    Database,
    Identity,
    guard_admin_removal,
    organization_record,
    require_roles,
)
from app.auth.errors import AuthError
from app.auth.service import HASHER, AuthService, Principal
from app.config import Settings
from app.database import database_engine
from app.main import create_app
from app.models import AuditLog, Job, Membership, Organization, SessionRecord, Transaction, User
from app.observability import SafeJSONFormatter

pytestmark = pytest.mark.database


@dataclass
class Harness:
    service: AuthService = field(repr=False)
    connection: Connection = field(repr=False)
    client: TestClient = field(repr=False)
    password: str = field(repr=False)
    user_id: UUID
    org_id: UUID
    email: str
    now: datetime

    def bootstrap(self) -> dict[str, str]:
        response = self.client.get("/api/v1/auth/csrf")
        assert response.status_code == 200
        return {
            "Origin": str(self.client.base_url).rstrip("/"),
            "X-CSRF-Token": response.json()["csrf_token"],
        }

    def login(self, **changes: object):
        return self.client.post(
            "/api/v1/auth/login",
            headers=self.bootstrap(),
            json={"email": self.email, "password": self.password, **changes},
        )


@pytest.fixture(scope="session")
def password_pair() -> tuple[str, str]:
    password = secrets.token_urlsafe(32)
    return password, HASHER.hash(password)


@pytest.fixture
def auth_configuration() -> Settings:
    return Settings(
        auth_secret=SecretStr(secrets.token_hex(32)),
        auth_cookie_secure=False,
        auth_allowed_origins="http://testserver",
        auth_login_ip_limit=100,
        auth_login_account_limit=100,
    )


def harness(
    engine: Engine, configuration: Settings, password_pair: tuple[str, str]
) -> Iterator[Harness]:
    with engine.connect() as connection:
        outer = connection.begin()
        auth = AuthService(configuration, engine)
        auth.sessions = sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        auth.limiter.namespace = f"sentinel:test:{uuid4()}"
        app = create_app(configuration, Mock(), auth)

        @app.get("/test/admin")
        def admin(principal: Annotated[Principal, Depends(require_roles("ADMIN"))]):
            return {"role": principal.role}

        @app.post("/test/mutation")
        def mutation(principal: Identity):
            return {"role": principal.role}

        @app.get("/test/jobs/{identifier}")
        def job(identifier: UUID, db: Database, principal: Identity):
            return {"id": str(organization_record(db, Job, identifier, principal).id)}

        @app.get("/test/transactions/{identifier}")
        def transaction(identifier: UUID, db: Database, principal: Identity):
            return {"id": str(organization_record(db, Transaction, identifier, principal).id)}

        with auth.sessions.begin() as db:
            org = Organization(name="Isolated fictional authentication organization")
            user = User(
                email=f"{uuid4()}@fixture.invalid",
                display_name="Fictional Auth User",
                password_hash=password_pair[1],
            )
            db.add_all([org, user])
            db.flush()
            db.add(Membership(organization_id=org.id, user_id=user.id, role="ANALYST"))
        with TestClient(app) as client:
            fixture = Harness(
                auth,
                connection,
                client,
                password_pair[0],
                user.id,
                org.id,
                user.email,
                datetime.now(UTC),
            )
            auth.clock = lambda: fixture.now
            try:
                yield fixture
            finally:
                keys = list(auth.limiter.client.scan_iter(f"{auth.limiter.namespace}:*"))
                if keys:
                    auth.limiter.client.delete(*keys)
                auth.limiter.close()
        outer.rollback()


@pytest.fixture
def auth(migrated_engine: Engine, auth_configuration: Settings, password_pair) -> Iterator[Harness]:
    yield from harness(migrated_engine, auth_configuration, password_pair)


def test_success_hash_cookie_me_and_logout(auth: Harness) -> None:
    response = auth.login(email=auth.email.upper())
    assert response.status_code == 200
    raw = auth.client.cookies.get(auth.service.settings.session_cookie)
    assert raw and raw not in response.text
    header = response.headers["set-cookie"]
    assert "HttpOnly" in header and "SameSite=lax" in header and "Path=/" in header
    assert "Secure" not in header and "Domain=" not in header
    assert "Max-Age=28800" in header
    with auth.service.sessions() as db:
        record = db.scalar(select(SessionRecord).where(SessionRecord.user_id == auth.user_id))
        assert hmac.compare_digest(record.token_hash, token_hash(raw))
        assert not hmac.compare_digest(record.token_hash, raw)
        assert record.expires_at - record.created_at == timedelta(hours=8)
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 1
    me = auth.client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["role"] == "ANALYST"
    assert me.json()["organization"]["id"] == str(auth.org_id)
    logout = auth.client.post("/api/v1/auth/logout", headers=auth.bootstrap())
    assert logout.status_code == 204 and "Max-Age=0" in logout.headers["set-cookie"]
    assert logout.content == b""
    auth.client.cookies.set(auth.service.settings.session_cookie, raw)
    assert auth.client.get("/api/v1/auth/me").status_code == 401
    with auth.service.sessions() as db:
        assert db.scalar(select(SessionRecord.revoked_at)) is not None
        assert sorted(db.scalars(select(AuditLog.action))) == ["AUTH_LOGIN", "AUTH_LOGOUT"]
        assert all(row.metadata_json == {} for row in db.scalars(select(AuditLog)))


def test_wrong_unknown_inactive_indistinguishable(auth: Harness) -> None:
    wrong = auth.login(password=secrets.token_urlsafe(32))
    unknown = auth.login(email=f"{uuid4()}@fixture.invalid")
    auth.connection.execute(update(User).where(User.id == auth.user_id).values(is_active=False))
    inactive = auth.login()
    for response in (wrong, unknown, inactive):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert response.json()["error"]["message"] == "Email or password is incorrect."
        assert "set-cookie" not in response.headers
    assert auth.connection.scalar(select(func.count()).select_from(SessionRecord)) == 0
    assert auth.connection.scalar(select(func.count()).select_from(AuditLog)) == 0


@pytest.mark.parametrize("token", [None, "invalid", "a" * 43])
def test_missing_invalid_sessions(auth: Harness, token: str | None) -> None:
    if token is not None:
        auth.client.cookies.set(auth.service.settings.session_cookie, token)
    assert auth.client.get("/api/v1/auth/me").status_code == 401
    assert auth.client.post("/api/v1/auth/logout").status_code == 401


@pytest.mark.parametrize(
    "cause", ["absolute", "idle", "revoked", "inactive", "removed", "ambiguous"]
)
def test_session_revalidated(auth: Harness, cause: str) -> None:
    assert auth.login().status_code == 200
    if cause == "absolute":
        auth.now += timedelta(hours=8)
    elif cause == "idle":
        auth.now += timedelta(minutes=30)
    elif cause == "revoked":
        auth.connection.execute(update(SessionRecord).values(revoked_at=auth.now))
    elif cause == "inactive":
        auth.connection.execute(update(User).where(User.id == auth.user_id).values(is_active=False))
    elif cause == "removed":
        auth.connection.execute(delete(Membership).where(Membership.user_id == auth.user_id))
    else:
        with auth.service.sessions.begin() as db:
            other = Organization(name="Fictional second organization")
            db.add(other)
            db.flush()
            db.add(Membership(user_id=auth.user_id, organization_id=other.id, role="ADMIN"))
    assert auth.client.get("/api/v1/auth/me").status_code == 401


def test_activity_slides_idle_but_not_absolute_lifetime(auth: Harness) -> None:
    assert auth.login().status_code == 200
    for _ in range(16):
        auth.now += timedelta(minutes=29)
        assert auth.client.get("/api/v1/auth/me").status_code == 200
    auth.now += timedelta(minutes=16)
    assert auth.client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize("role,status", [("ANALYST", 403), ("RISK_MANAGER", 403), ("ADMIN", 200)])
def test_roles_and_live_changes(auth: Harness, role: str, status: int) -> None:
    assert auth.login().status_code == 200
    auth.connection.execute(
        update(Membership).where(Membership.user_id == auth.user_id).values(role=role)
    )
    assert auth.client.get("/test/admin").status_code == status
    assert auth.client.get("/api/v1/auth/me").json()["role"] == role
    assert auth.client.post("/test/mutation", headers=auth.bootstrap()).status_code == 200
    auth.connection.execute(
        update(Membership).where(Membership.user_id == auth.user_id).values(role="ANALYST")
    )
    assert auth.client.get("/test/admin").status_code == 403


@pytest.mark.parametrize(
    "field,value", [("role", "ADMIN"), ("organization_id", str(uuid4())), ("is_active", True)]
)
def test_overposting_is_rejected(auth: Harness, field: str, value: object) -> None:
    assert auth.login(**{field: value}).status_code == 422
    assert auth.connection.scalar(select(func.count()).select_from(SessionRecord)) == 0


def test_forged_headers_cannot_escalate(auth: Harness) -> None:
    assert auth.login().status_code == 200
    forged = {"X-Role": "ADMIN", "X-Organization-ID": str(uuid4()), "X-User-ID": str(uuid4())}
    assert auth.client.get("/test/admin", headers=forged).status_code == 403
    assert auth.client.get("/api/v1/auth/me", headers=forged).json()["organization"]["id"] == str(
        auth.org_id
    )


@pytest.mark.parametrize("route", ["login", "logout", "mutation"])
@pytest.mark.parametrize(
    "attack",
    ["missing-origin", "evil-origin", "null-origin", "missing-token", "wrong-token", "fetch-site"],
)
def test_csrf_rejections(auth: Harness, route: str, attack: str) -> None:
    if route != "login":
        assert auth.login().status_code == 200
    headers = auth.bootstrap()
    if attack == "missing-origin":
        del headers["Origin"]
    elif attack in {"evil-origin", "null-origin"}:
        headers["Origin"] = "https://evil.invalid" if attack == "evil-origin" else "null"
    elif attack == "missing-token":
        del headers["X-CSRF-Token"]
    elif attack == "wrong-token":
        headers["X-CSRF-Token"] = "0" * 64
    else:
        headers["Sec-Fetch-Site"] = "cross-site"
    path = "/test/mutation" if route == "mutation" else f"/api/v1/auth/{route}"
    response = auth.client.post(
        path, headers=headers, json={"email": auth.email, "password": auth.password}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_REJECTED"
    if route == "logout":
        assert auth.client.get("/api/v1/auth/me").status_code == 200


def test_preauth_tampering_and_expiry(auth: Harness) -> None:
    headers = auth.bootstrap()
    auth.now += timedelta(seconds=601)
    assert (
        auth.client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": auth.email, "password": auth.password},
        ).status_code
        == 403
    )
    headers = auth.bootstrap()
    auth.client.cookies.clear()
    auth.client.cookies.set(auth.service.settings.preauth_cookie, "attacker-controlled")
    assert (
        auth.client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": auth.email, "password": auth.password},
        ).status_code
        == 403
    )


def test_session_rotation_and_csrf_binding(auth: Harness) -> None:
    first = auth.login()
    old = auth.client.cookies.get(auth.service.settings.session_cookie)
    second = auth.login()
    assert second.status_code == 200
    new = auth.client.cookies.get(auth.service.settings.session_cookie)
    assert not hmac.compare_digest(old, new)
    assert (
        auth.client.post(
            "/test/mutation",
            headers={"Origin": "http://testserver", "X-CSRF-Token": first.json()["csrf_token"]},
        ).status_code
        == 403
    )
    auth.client.cookies.clear()
    auth.client.cookies.set(
        auth.service.settings.session_cookie, old, domain="testserver.local", path="/"
    )
    assert auth.client.get("/api/v1/auth/me").status_code == 401
    bootstrap = auth.client.get("/api/v1/auth/csrf")
    assert bootstrap.status_code == 200
    assert auth.client.cookies.get(auth.service.settings.session_cookie) is None


def test_cross_organization_lookup_is_indistinguishable_from_missing(auth: Harness) -> None:
    assert auth.login().status_code == 200
    with auth.service.sessions.begin() as db:
        other = Organization(name="Fictional other tenant")
        db.add(other)
        db.flush()
        ids = []
        for org in [auth.org_id, other.id]:
            job = Job(
                organization_id=org,
                requested_by=auth.user_id,
                type="REPORT_EXPORT",
                status="QUEUED",
            )
            transaction = Transaction(
                organization_id=org,
                external_id="test-only",
                customer_ref="fictional",
                occurred_at=auth.now,
                amount=10,
                currency="INR",
                merchant_category="synthetic",
                country_code="IN",
                channel="WEB",
                source="SINGLE",
            )
            db.add_all([job, transaction])
            db.flush()
            ids.append((job.id, transaction.id))
    for index, route in enumerate(["jobs", "transactions"]):
        assert auth.client.get(f"/test/{route}/{ids[0][index]}").status_code == 200
        forbidden = auth.client.get(f"/test/{route}/{ids[1][index]}")
        missing = auth.client.get(f"/test/{route}/{uuid4()}")
        assert forbidden.status_code == missing.status_code == 404
        assert forbidden.json()["error"]["message"] == missing.json()["error"]["message"]
        assert str(other.id) not in forbidden.text


def test_last_active_admin_guard(auth: Harness) -> None:
    auth.connection.execute(update(Membership).values(role="ADMIN"))
    with pytest.raises(AuthError) as error, auth.service.sessions.begin() as db:
        guard_admin_removal(db, auth.org_id, auth.user_id)
    assert error.value.status == 409
    with auth.service.sessions.begin() as db:
        other = User(
            email=f"{uuid4()}@fixture.invalid",
            display_name="Fictional second admin",
            password_hash=auth.service.dummy_hash,
        )
        db.add(other)
        db.flush()
        db.add(Membership(organization_id=auth.org_id, user_id=other.id, role="ADMIN"))
    with auth.service.sessions.begin() as db:
        guard_admin_removal(db, auth.org_id, auth.user_id)


def test_rate_limits_and_forwarded_ip_not_trusted(auth: Harness) -> None:
    auth.service.settings.auth_login_account_limit = 2
    for _ in range(2):
        assert auth.login(password=secrets.token_urlsafe(32)).status_code == 401
    response = auth.login()
    assert response.status_code == 429 and 1 <= int(response.headers["retry-after"]) <= 300
    auth.service.settings.auth_login_ip_limit = 2
    response = auth.client.post(
        "/api/v1/auth/login",
        headers={**auth.bootstrap(), "X-Forwarded-For": "192.0.2.99"},
        json={"email": f"{uuid4()}@fixture.invalid", "password": auth.password},
    )
    assert response.status_code == 429
    keys = list(auth.service.limiter.client.scan_iter(f"{auth.service.limiter.namespace}:*"))
    assert all(0 < auth.service.limiter.client.ttl(key) <= 300 for key in keys)
    assert all(auth.email.encode() not in key and b"testclient" not in key for key in keys)


def test_atomic_rate_admission_under_concurrency(auth: Harness) -> None:
    auth.service.settings.auth_login_account_limit = 5

    def attempt(_):
        try:
            auth.service.limiter.admit("same-peer", auth.email)
            return True
        except AuthError as error:
            assert error.status == 429
            return False

    with ThreadPoolExecutor(max_workers=16) as executor:
        assert sum(executor.map(attempt, range(32))) == 5


def test_redis_unavailable_fails_closed_but_existing_sessions_work(
    auth: Harness, monkeypatch
) -> None:
    assert auth.login().status_code == 200
    monkeypatch.setattr(
        auth.service.limiter.client,
        "eval",
        Mock(side_effect=RedisConnectionError("secret outage detail")),
    )
    response = auth.login()
    assert response.status_code == 503 and "secret outage detail" not in response.text
    assert auth.client.get("/api/v1/auth/me").status_code == 200
    assert auth.client.post("/api/v1/auth/logout", headers=auth.bootstrap()).status_code == 204


def test_security_logs_and_audit_exclude_secrets(auth: Harness, caplog, monkeypatch) -> None:
    monkeypatch.setattr(logging.getLogger("sentinelai"), "propagate", True)
    caplog.set_level(logging.INFO, logger="sentinelai")
    response = auth.login()
    raw = auth.client.cookies.get(auth.service.settings.session_cookie)
    assert auth.login(password=secrets.token_urlsafe(32)).status_code == 401
    rendered = "\n".join(SafeJSONFormatter().format(record) for record in caplog.records)
    assert '"action": "auth_login"' in rendered
    assert '"status": 401' in rendered
    with auth.service.sessions() as db:
        rendered += repr([row.metadata_json for row in db.scalars(select(AuditLog))])
    for secret in [
        auth.password,
        raw,
        token_hash(raw),
        response.json()["csrf_token"],
        auth.service.dummy_hash,
        auth.email,
    ]:
        assert secret not in rendered


def test_actual_application_role_and_append_only_audit(
    migrated_engine, auth_configuration, password_pair
) -> None:
    engine = database_engine(auth_configuration.database_url)
    try:
        for fixture in harness(engine, auth_configuration, password_pair):
            assert fixture.connection.scalar(text("SELECT current_user")) == "sentinel_app"
            assert fixture.login().status_code == 200
            assert fixture.client.get("/api/v1/auth/me").status_code == 200
            assert (
                fixture.client.post("/api/v1/auth/logout", headers=fixture.bootstrap()).status_code
                == 204
            )
            for statement in [
                "DELETE FROM audit_logs",
                "UPDATE audit_logs SET action='FORGED'",
                "CREATE TABLE forbidden(id int)",
            ]:
                with pytest.raises(ProgrammingError), fixture.connection.begin_nested():
                    fixture.connection.execute(text(statement))
    finally:
        engine.dispose()


def test_cleanup_preserves_active_sessions(auth: Harness) -> None:
    assert auth.login().status_code == 200
    with auth.service.sessions.begin() as db:
        for expired in [True, False]:
            db.add(
                SessionRecord(
                    user_id=auth.user_id,
                    token_hash=token_hash(new_token()),
                    created_at=auth.now - timedelta(days=2),
                    expires_at=auth.now - timedelta(days=1)
                    if expired
                    else auth.now + timedelta(hours=1),
                    revoked_at=None if expired else auth.now - timedelta(days=1),
                )
            )
    assert cleanup_sessions(auth.connection, auth.now, batch_size=1, batches=1) == 1
    assert cleanup_sessions(auth.connection, auth.now) == 1
    assert auth.client.get("/api/v1/auth/me").status_code == 200


def test_audit_failure_rolls_back_session_and_sends_no_cookie(auth: Harness, monkeypatch) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    def failure(*args):
        raise SQLAlchemyError("private database detail")

    monkeypatch.setattr(auth.service, "audit", failure)
    response = auth.login()
    assert response.status_code == 503
    assert "private database detail" not in response.text
    assert "set-cookie" not in response.headers
    assert auth.connection.scalar(select(func.count()).select_from(SessionRecord)) == 0


def test_logout_audit_failure_preserves_session(auth: Harness, monkeypatch) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    assert auth.login().status_code == 200
    monkeypatch.setattr(auth.service, "audit", Mock(side_effect=SQLAlchemyError("private")))
    response = auth.client.post("/api/v1/auth/logout", headers=auth.bootstrap())
    assert response.status_code == 503
    assert "set-cookie" not in response.headers
    assert auth.client.get("/api/v1/auth/me").status_code == 200
    assert auth.connection.scalar(select(SessionRecord.revoked_at)) is None


def test_https_production_cookie_flags(migrated_engine, auth_configuration, password_pair) -> None:
    configuration = Settings(
        **{
            **auth_configuration.model_dump(),
            "app_env": "production",
            "auth_allowed_origins": "https://testserver",
            "auth_cookie_secure": True,
        }
    )
    for fixture in harness(migrated_engine, configuration, password_pair):
        # Secure-cookie behavior requires the actual HTTPS URL in the test transport.
        fixture.client.base_url = "https://testserver"
        response = fixture.login()
        assert response.status_code == 200
        headers = response.headers.get_list("set-cookie")
        assert all(
            "Secure" in value and "HttpOnly" in value and "SameSite=lax" in value
            for value in headers
        )
        assert all("Domain=" not in value and "Path=/" in value for value in headers)
        assert headers[0].startswith("__Host-sentinel_session=")
        assert fixture.client.get("/api/v1/auth/me").status_code == 200
        logout = fixture.client.post("/api/v1/auth/logout", headers=fixture.bootstrap())
        assert logout.status_code == 204 and logout.content == b""
        assert "Secure" in logout.headers["set-cookie"]
        assert fixture.client.cookies.get(configuration.session_cookie) is None


def test_real_redis_connection_failure_and_recovery(auth: Harness) -> None:
    from app.auth.limiter import LoginLimiter

    unavailable = LoginLimiter(
        auth.service.settings.model_copy(update={"redis_port": 1}), auth.service.csrf
    )
    try:
        with pytest.raises(AuthError) as error:
            unavailable.admit("peer", auth.email)
        assert error.value.status == 503
    finally:
        unavailable.close()
    auth.service.limiter.admit("peer", auth.email)


@pytest.mark.parametrize("role", ["ANALYST", "RISK_MANAGER", "ADMIN"])
def test_org_guards_cover_cases_alerts_models_datasets_and_report_jobs(
    auth: Harness, role: str
) -> None:
    from app.models import Alert, Case, Dataset, ModelVersion, ScoringResult

    auth.connection.execute(update(Membership).values(role=role))
    assert auth.login().status_code == 200
    raw = auth.client.cookies.get(auth.service.settings.session_cookie)
    with auth.service.sessions.begin() as db:
        principal = auth.service.resolve(db, raw)
        foreign = Organization(name="Isolated foreign fixture")
        db.add(foreign)
        db.flush()
        for organization_id in [auth.org_id, foreign.id]:
            dataset = Dataset(
                organization_id=organization_id,
                uploaded_by=auth.user_id,
                purpose="TRAINING",
                source_kind="SYNTHETIC",
                original_filename="fixture.csv",
                object_key="no-real-object",
                sha256="0" * 64,
                size_bytes=1,
                status="VALIDATED",
            )
            transaction = Transaction(
                organization_id=organization_id,
                external_id="guard-fixture",
                customer_ref="synthetic",
                occurred_at=auth.now,
                amount=1,
                currency="INR",
                merchant_category="fixture",
                country_code="IN",
                channel="WEB",
                source="SINGLE",
            )
            job = Job(
                organization_id=organization_id,
                requested_by=auth.user_id,
                type="REPORT_EXPORT",
                status="QUEUED",
            )
            db.add_all([dataset, transaction, job])
            db.flush()
            model = ModelVersion(
                organization_id=organization_id,
                training_dataset_id=dataset.id,
                version_label="fixture-only",
                algorithm="not-trained",
                artifact_key="no-artifact",
                artifact_sha256="0" * 64,
                feature_schema_json={},
                metrics_json={},
                trained_at=auth.now,
            )
            db.add(model)
            db.flush()
            score = ScoringResult(
                transaction_id=transaction.id,
                model_version_id=model.id,
                risk_score=0,
                risk_band="LOW",
                supervised_probability=0,
                anomaly_percentile=0,
                rule_signal=0,
                explanation_status="PARTIAL",
                explanation_json={},
                settings_snapshot_json={},
                latency_ms=0,
            )
            db.add(score)
            db.flush()
            alert = Alert(
                organization_id=organization_id,
                scoring_result_id=score.id,
                status="IN_CASE",
                reason_summary="Isolated authorization fixture",
            )
            db.add(alert)
            db.flush()
            case = Case(
                organization_id=organization_id,
                alert_id=alert.id,
                created_by=auth.user_id,
                status="OPEN",
            )
            db.add(case)
            db.flush()
            for record in [dataset, transaction, job, model, alert, case]:
                if organization_id == auth.org_id:
                    assert (
                        organization_record(db, type(record), record.id, principal).id == record.id
                    )
                else:
                    with pytest.raises(AuthError) as error:
                        organization_record(db, type(record), record.id, principal)
                    assert error.value.status == 404


def test_transaction_completion_failure_never_sends_session_cookie(
    auth: Harness, monkeypatch
) -> None:
    from contextlib import contextmanager

    from sqlalchemy.exc import SQLAlchemyError

    headers = auth.bootstrap()
    original_begin = auth.service.sessions.begin

    @contextmanager
    def failed_completion():
        with original_begin() as db:
            yield db
            raise SQLAlchemyError("private commit detail")

    monkeypatch.setattr(auth.service.sessions, "begin", failed_completion)
    response = auth.client.post(
        "/api/v1/auth/login", headers=headers, json={"email": auth.email, "password": auth.password}
    )
    assert response.status_code == 503
    assert "set-cookie" not in response.headers
    assert "private commit detail" not in response.text
    assert auth.connection.scalar(select(func.count()).select_from(SessionRecord)) == 0
    assert auth.connection.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_rate_budget_expires(auth: Harness) -> None:
    auth.service.settings.auth_login_account_limit = 1
    auth.service.limiter.admit("peer", auth.email)
    with pytest.raises(AuthError) as error:
        auth.service.limiter.admit("peer", auth.email)
    assert error.value.status == 429
    # Expire only this test's keys; never flush any shared Redis database.
    keys = list(auth.service.limiter.client.scan_iter(f"{auth.service.limiter.namespace}:*"))
    for key in keys:
        auth.service.limiter.client.expire(key, 0)
    auth.service.limiter.admit("peer", auth.email)
