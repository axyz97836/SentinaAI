import json
import logging
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.health import DependencyProbe
from app.main import create_app
from app.observability import SafeJSONFormatter


@pytest.mark.parametrize("available", [True, False])
def test_liveness_does_not_depend_on_infrastructure(settings: Settings, available: bool) -> None:
    probe = Mock()
    probe.ready.return_value = available
    with TestClient(create_app(settings, probe)) as client:
        response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    probe.ready.assert_not_called()
    UUID(response.headers["x-request-id"])
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("available,status", [(True, 200), (False, 503)])
def test_readiness_reports_actual_state(settings: Settings, available: bool, status: int) -> None:
    probe = Mock()
    probe.ready.return_value = available
    with TestClient(create_app(settings, probe)) as client:
        response = client.get("/api/v1/health/ready")
    assert response.status_code == status
    probe.ready.assert_called_once()
    if available:
        assert response.json() == {"status": "ready"}
    else:
        error = response.json()["error"]
        assert error["code"] == "DEPENDENCY_UNAVAILABLE"
        assert error["request_id"] == response.headers["x-request-id"]


@pytest.mark.parametrize("dependency", ["database", "cache", "objects"])
def test_each_dependency_failure_prevents_readiness(settings: Settings, dependency: str) -> None:
    probe = DependencyProbe(settings)
    probe.database = Mock()
    probe.cache = Mock()
    probe.objects = Mock()
    getattr(probe, dependency).side_effect = RuntimeError("secret-should-not-be-returned")
    try:
        with TestClient(create_app(settings, probe)) as client:
            response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert "secret-should-not-be-returned" not in response.text
    finally:
        probe.close()


def test_unexpected_error_is_redacted(settings: Settings) -> None:
    probe = Mock()
    probe.ready.side_effect = RuntimeError("password=do-not-leak")
    with TestClient(create_app(settings, probe)) as client:
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "do-not-leak" not in response.text


def test_unknown_route_and_cors_do_not_expose_details(settings: Settings) -> None:
    with TestClient(create_app(settings, Mock())) as client:
        response = client.get(
            "/unknown?token=private", headers={"Origin": "https://untrusted.test"}
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert "access-control-allow-origin" not in response.headers
    assert "private" not in response.text


def test_logging_uses_only_allowlisted_fields() -> None:
    record = logging.LogRecord("sentinelai", logging.ERROR, "", 0, "password=private", (), None)
    record.request_id = "request-reference"
    record.cookie = "do-not-log"
    result = SafeJSONFormatter().format(record)
    assert json.loads(result)["request_id"] == "request-reference"
    assert "private" not in result
    assert "do-not-log" not in result
