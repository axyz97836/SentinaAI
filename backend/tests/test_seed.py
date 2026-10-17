from pathlib import Path
from unittest.mock import Mock

import pytest

from app import seed


@pytest.mark.parametrize("environment", ["production", "staging", "test", ""])
def test_seed_cli_refuses_non_local_before_connecting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, environment: str
) -> None:
    target = tmp_path / "credentials.json"
    connect = Mock(side_effect=AssertionError("Must not connect"))
    monkeypatch.setattr(seed, "database_engine", connect)
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setattr("sys.argv", ["seed", "--credentials-file", str(target)])
    assert seed.main() == 1
    connect.assert_not_called()
    assert not target.exists()
