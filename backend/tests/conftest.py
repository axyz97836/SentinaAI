import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    # Isolated test values. These are not credentials for a running service.
    return Settings(
        app_env="test",
        auth_secret="isolated-test-signing-key-" + "x" * 64,
        auth_cookie_secure=False,
        auth_allowed_origins="http://testserver",
        app_db_password="test-database-value-" + "x" * 32,
        redis_password="test-broker-value-" + "x" * 32,
        s3_access_key="test-access-value-" + "x" * 16,
        s3_secret_key="test-storage-value-" + "x" * 32,
    )
