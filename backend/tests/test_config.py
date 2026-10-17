import pytest
from pydantic import ValidationError

from app.config import Settings


def test_configuration_hides_secrets(settings: Settings) -> None:
    assert settings.app_db_password.get_secret_value() not in repr(settings)
    assert settings.s3_secret_key.get_secret_value() not in repr(settings)
    assert settings.app_db_password.get_secret_value() not in str(settings.database_url)


def test_missing_secrets_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_DB_PASSWORD", "REDIS_PASSWORD", "S3_ACCESS_KEY", "S3_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_production_environment_is_rejected(settings: Settings) -> None:
    values = settings.model_dump()
    values["app_env"] = "production"
    with pytest.raises(ValidationError):
        Settings(**values)
