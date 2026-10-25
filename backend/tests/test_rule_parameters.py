"""Strict configuration boundaries without a database."""

import pytest
from pydantic import ValidationError

from app.scoring.configuration import RuleUpdate, SettingsUpdate
from app.scoring.rules import validate_parameters


@pytest.mark.parametrize(
    "code,params",
    [
        ("AMOUNT_OUTLIER", {"multiplier": 3, "min_history": 5}),
        ("HIGH_VELOCITY", {"window_minutes": 10, "count_threshold": 5}),
        ("DEVICE_CHANGE", {}),
    ],
)
def test_supported_parameter_shapes(code, params):
    assert validate_parameters(code, params) == params


@pytest.mark.parametrize(
    "code,params",
    [
        ("UNKNOWN", {}),
        ("DEVICE_CHANGE", {"secret": "not-allowed"}),
        ("AMOUNT_OUTLIER", {"multiplier": True, "min_history": 1}),
        ("AMOUNT_OUTLIER", {"multiplier": float("nan"), "min_history": 1}),
        ("AMOUNT_OUTLIER", {"multiplier": 1, "min_history": 1}),
        ("AMOUNT_OUTLIER", {"multiplier": 101, "min_history": 1}),
        ("AMOUNT_OUTLIER", {"multiplier": 3, "min_history": 0}),
        ("AMOUNT_OUTLIER", {"multiplier": 3, "min_history": 101}),
        ("AMOUNT_OUTLIER", {"multiplier": "3", "min_history": 1}),
        ("HIGH_VELOCITY", {"window_minutes": True, "count_threshold": 1}),
        ("HIGH_VELOCITY", {"window_minutes": 60, "count_threshold": 1}),
        ("HIGH_VELOCITY", {"window_minutes": 10, "count_threshold": 0}),
        ("HIGH_VELOCITY", {"window_minutes": 10, "count_threshold": 1001}),
        ("HIGH_VELOCITY", {"window_minutes": 10, "count_threshold": 1.5}),
    ],
)
def test_malformed_rule_parameters(code, params):
    with pytest.raises(ValueError):
        validate_parameters(code, params)


@pytest.mark.parametrize(
    "change",
    [
        {"medium_threshold": 0},
        {"high_threshold": 40},
        {"critical_threshold": 70},
        {"alert_threshold": -1},
        {"alert_threshold": 101},
        {"version": 0},
        {"version": True},
        {"medium_threshold": "40"},
        {"organization_id": "forbidden"},
    ],
)
def test_threshold_validation(change):
    with pytest.raises(ValidationError):
        SettingsUpdate.model_validate(
            {
                "medium_threshold": 40,
                "high_threshold": 70,
                "critical_threshold": 85,
                "alert_threshold": 70,
                "version": 1,
                **change,
            }
        )


def test_independent_alert_threshold_and_partial_rule_edit():
    assert (
        SettingsUpdate(
            medium_threshold=40,
            high_threshold=70,
            critical_threshold=85,
            alert_threshold=0,
            version=1,
        ).alert_threshold
        == 0
    )
    assert RuleUpdate(enabled=False, version=1).enabled is False


@pytest.mark.parametrize(
    "change",
    [
        {},
        {"enabled": None},
        {"enabled": "false"},
        {"parameters_json": None},
        {"parameters_json": []},
        {"code": "DEVICE_CHANGE"},
    ],
)
def test_rule_patch_rejects_null_empty_or_unknown_fields(change):
    with pytest.raises(ValidationError):
        RuleUpdate.model_validate({"version": 1, **change})
