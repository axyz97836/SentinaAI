from decimal import Decimal
from unittest.mock import Mock

import numpy as np
import pytest
from pydantic import ValidationError

from app.ingestion.validation import InvalidCSV
from app.ml.training import WEIGHTS, BaselineBundle, features
from app.scoring.calculation import band, component, composite
from app.scoring.schema import TransactionInput

PAYLOAD = {
    "external_id": "syn-single",
    "customer_ref": "customer-fictional",
    "occurred_at": "2026-01-23T10:00:00Z",
    "amount": "100.00",
    "currency": "INR",
    "merchant_category": "grocery",
    "country_code": "IN",
    "channel": "WEB",
}
THRESHOLDS = {"medium_threshold": 40, "high_threshold": 70, "critical_threshold": 85}


@pytest.mark.parametrize(
    "field,value",
    [
        ("fraud_label", 1),
        ("risk_score", 90),
        ("role", "ADMIN"),
        ("organization_id", "bad"),
        ("model_version_id", "bad"),
        ("amount", True),
        ("amount", "NaN"),
        ("amount", -1),
        ("amount", "1.001"),
        ("amount", "1000000000000"),
        ("customer_ref", "person@example.test"),
        ("device_ref", "123456789"),
        ("currency", "XYZ"),
        ("country_code", "ZZ"),
        ("channel", "OTHER"),
        ("occurred_at", "2026-01-23T10:00:00"),
    ],
)
def test_invalid_canonical_fields(field, value):
    with pytest.raises(ValidationError):
        TransactionInput.model_validate({**PAYLOAD, field: value})


def test_canonical_replay_normalization():
    a = TransactionInput.model_validate(PAYLOAD)
    b = TransactionInput.model_validate(
        {
            **PAYLOAD,
            "amount": 100,
            "device_ref": "",
            "occurred_at": "2026-01-23T10:00:00.000000+00:00",
        }
    )
    assert a.values() == b.values()
    assert a.row()["amount"] == "100.00"
    assert "fraud_label" not in a.row()


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, "LOW"),
        (39, "LOW"),
        (40, "MEDIUM"),
        (69, "MEDIUM"),
        (70, "HIGH"),
        (84, "HIGH"),
        (85, "CRITICAL"),
        (100, "CRITICAL"),
    ],
)
def test_band_boundaries(score, expected):
    assert band(score, THRESHOLDS) == expected


def test_decimal_rounding_and_configured_weights():
    assert composite(Decimal("0.5"), Decimal("0.1"), Decimal(1), WEIGHTS) == 48
    assert composite(Decimal("0.5"), Decimal("0.1"), Decimal(0), WEIGHTS) == 32
    assert composite(Decimal(1), Decimal(1), Decimal(0), WEIGHTS) == 85
    assert (
        composite(
            Decimal("0.125"), Decimal(0), Decimal(0), {"supervised": 1, "anomaly": 0, "rules": 0}
        )
        == 12
    )
    assert component(0.1234567) == Decimal("0.123457")
    assert (
        band(40, {"medium_threshold": 50, "high_threshold": 80, "critical_threshold": 95}) == "LOW"
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.01, 1.01])
def test_nonfinite_or_unbounded_components(value):
    with pytest.raises(InvalidCSV):
        component(value)


@pytest.mark.parametrize(
    "probabilities,scores",
    [
        ([[0.2, 0.8]], [float("nan")]),
        ([[0.2, 0.8]], [float("inf")]),
        ([[0.2, 1.8]], [0]),
        ([[0.2, 0.8], [0.2, 0.8]], [0]),
        ([[0.2, 0.8]], [[0]]),
        ([[0.2, float("nan")]], [0]),
    ],
)
def test_inference_rejects_invalid_dimensions_or_raw_outputs(probabilities, scores):
    classifier, anomaly = Mock(), Mock()
    classifier.classes_ = np.array([0, 1])
    classifier.predict_proba.return_value = probabilities
    anomaly.score_samples.return_value = scores
    bundle = BaselineBundle(classifier, anomaly, np.array([-1.0, 0.0, 1.0]), {}, {}, {})
    with pytest.raises(InvalidCSV, match="MODEL_OUTPUT_INVALID"):
        bundle.components([PAYLOAD])


def test_static_feature_order_and_training_percentile():
    classifier, anomaly = Mock(), Mock()
    classifier.classes_ = np.array([0, 1])
    classifier.predict_proba.return_value = [[0.2, 0.8]]
    anomaly.score_samples.return_value = [-2.0]
    bundle = BaselineBundle(classifier, anomaly, np.array([1.0, 2.0, 3.0, 4.0]), {}, {}, {})
    probability, percentile = bundle.components([PAYLOAD])
    assert probability.tolist() == [0.8] and percentile.tolist() == [0.5]
    assert features([PAYLOAD])[0, 5:].tolist() == ["INR", "IN", "WEB", "grocery"]
    assert np.array_equal(
        features([PAYLOAD]), features([{**PAYLOAD, "fraud_label": "1", "device_ref": "changed"}])
    )
