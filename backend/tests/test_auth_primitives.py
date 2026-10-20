import secrets
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth.crypto import CSRF, new_token, token_hash
from app.auth.service import AuthService
from app.config import Settings
from app.main import create_app


def test_session_entropy_and_one_way_representation() -> None:
    tokens = {new_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(value) == 43 and len(token_hash(value)) == 64 for value in tokens)
    assert all(value not in token_hash(value) for value in tokens)


@pytest.mark.parametrize("value", ["", "short", "x" * 44, "é" * 43, "a/b" * 14 + "x"])
def test_malformed_bearer_tokens(value: str) -> None:
    assert token_hash(value) is None


def test_preauth_signature_lifetime_and_purpose() -> None:
    csrf = CSRF(secrets.token_hex(32))
    value = csrf.issue_preauth(1000)
    assert csrf.valid_preauth(value, 1000)
    assert csrf.valid_preauth(value, 1600)
    assert not csrf.valid_preauth(value, 1601)
    assert not csrf.valid_preauth(value, 994)
    assert not csrf.valid_preauth(value[:-1] + "z", 1000)
    assert not CSRF(secrets.token_hex(32)).valid_preauth(value, 1000)
    assert not csrf.matches(
        csrf.proof("preauth-header", value), csrf.proof("session-header", value)
    )
    assert not csrf.matches("é" * 64, csrf.proof("session-header", value))


@pytest.mark.parametrize("value", ["", ".", "1.x.y", "9" * 200, "١.a.b", "a.b.c"])
def test_malformed_preauth_cookies(value: str) -> None:
    assert not CSRF(secrets.token_hex(32)).valid_preauth(value, 1000)


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "null",
        "http://localhost:3000/",
        "https://user:password@example.invalid",
        "https://example.invalid?query=1",
        "https://example.invalid#fragment",
        "",
    ],
)
def test_bad_origin_configuration(settings: Settings, origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(**{**settings.model_dump(), "auth_allowed_origins": origin})


@pytest.mark.parametrize(
    "secure,origin,allowed",
    [
        (False, "https://app.example.invalid", False),
        (True, "http://app.example.invalid", False),
        (True, "https://app.example.invalid", True),
    ],
)
def test_production_cookie_policy(
    settings: Settings, secure: bool, origin: str, allowed: bool
) -> None:
    values = {
        **settings.model_dump(),
        "app_env": "production",
        "auth_cookie_secure": secure,
        "auth_allowed_origins": origin,
    }
    if not allowed:
        with pytest.raises(ValidationError):
            Settings(**values)
    else:
        configuration = Settings(**values)
        assert configuration.session_cookie.startswith("__Host-")
        assert configuration.preauth_cookie.startswith("__Host-")


def test_auth_key_required_and_hidden(settings: Settings) -> None:
    assert settings.auth_secret.get_secret_value() not in repr(settings)
    with pytest.raises(ValueError, match="AUTH_SECRET"):
        AuthService(settings.model_copy(update={"auth_secret": None}))


def test_insecure_remote_and_unbounded_timeout_rejected(settings: Settings) -> None:
    for updates in [
        {"auth_allowed_origins": "http://app.example.invalid"},
        {"auth_session_seconds": 86401},
        {"auth_idle_seconds": 30000},
        {"auth_login_ip_limit": 0},
    ]:
        with pytest.raises(ValidationError):
            Settings(**{**settings.model_dump(), **updates})


@pytest.mark.parametrize("chunked", [True, False])
def test_auth_body_limit_counts_actual_bytes(settings: Settings, chunked: bool) -> None:
    with TestClient(create_app(settings, Mock())) as client:
        content = iter([b"x" * 2048, b"y" * 2049]) if chunked else b"x" * 4097
        response = client.post("/api/v1/auth/login", content=content)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "BODY_TOO_LARGE"
    assert response.headers["cache-control"] == "no-store"


def test_forwarded_headers_do_not_redefine_allowed_origin(settings: Settings) -> None:
    with TestClient(create_app(settings, Mock())) as client:
        response = client.get(
            "/api/v1/auth/csrf",
            headers={
                "Origin": "https://evil.invalid",
                "X-Forwarded-Host": "testserver",
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "127.0.0.1",
            },
        )
    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers
