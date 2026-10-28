from dataclasses import replace
from unittest.mock import Mock

import numpy as np
import pytest
from test_model_training import bundle as bundle
from test_model_training import rows as rows

from app.ingestion.validation import InvalidCSV
from app.ml.attribution import build_attribution, explain_supervised
from app.ml.data import chronological_split
from app.ml.runtime import require_authoritative_runtime
from app.ml.training import features


@pytest.fixture(scope="module")
def reference(bundle, rows):
    return build_attribution(bundle, rows)


def test_real_shap_exact_feature_alignment_signed_values_and_additivity(bundle, rows, reference):
    original = [values.copy() for values in bundle.components(rows)]
    classifier = bundle.supervised.named_steps["classifier"]
    for row in rows[::17]:
        probability = float(bundle.components([row])[0][0])
        result = explain_supervised(bundle, row, reference, probability)
        assert result["available"] and result["units"] == "log_odds"
        assert (
            result["method"] == "SHAP_LINEAR_INTERVENTIONAL"
            and result["library_version"] == "0.54.1"
        )
        matrix = bundle.supervised.named_steps["preprocessing"].transform(features([row]))
        expected = classifier.coef_[0] * (matrix[0] - reference.mean)
        actual = reference.explainer.shap_values(matrix)[0]
        np.testing.assert_allclose(actual, expected, rtol=0, atol=0)
        selected = result["top_features"]
        assert 0 < len(selected) <= 5
        assert [abs(f["contribution"]) for f in selected] == sorted(
            [abs(f["contribution"]) for f in selected], reverse=True
        )
        for feature in selected:
            index = reference.names.index(feature["transformed_feature"])
            assert feature["feature"] == reference.labels[index]
            assert feature["contribution"] == actual[index]
        assert (
            abs(
                result["base_value"]
                + result["remaining_features_contribution"]
                + sum(f["contribution"] for f in selected)
                - result["model_output"]
            )
            < 1e-10
        )
        assert result["reference_count"] == 1200 and result["feature_count"] == len(reference.names)
    for before, after in zip(original, bundle.components(rows), strict=True):
        np.testing.assert_array_equal(before, after)


def test_background_uses_only_training_fold_and_no_refit(bundle, rows, reference):
    training, _, _ = chronological_split(rows)
    expected = (
        bundle.supervised.named_steps["preprocessing"].transform(features(training)).mean(axis=0)
    )
    np.testing.assert_array_equal(reference.mean, expected)
    changed = [dict(row) for row in rows]
    for row in changed[1200:]:
        row.update(amount="999999999999.99", merchant_category="held-out-only")
        row["fraud_label"] = str(1 - int(row["fraud_label"]))
    other = build_attribution(bundle, changed)
    np.testing.assert_array_equal(other.mean, reference.mean)
    row = rows[-1]
    p = float(bundle.components([row])[0][0])
    assert explain_supervised(bundle, row, other, p) == explain_supervised(
        bundle, row, reference, p
    )
    assert all("held-out-only" not in name for name in other.names)


def test_labels_identifiers_do_not_affect_explanations(bundle, rows, reference):
    row = rows[-1]
    changed = {
        **row,
        "fraud_label": "1",
        "external_id": "other",
        "customer_ref": "other",
        "device_ref": "other",
    }
    p = float(bundle.components([row])[0][0])
    assert explain_supervised(bundle, row, reference, p) == explain_supervised(
        bundle, changed, reference, p
    )


@pytest.mark.parametrize(
    "problem",
    ["shape", "nan", "base", "additivity", "feature_order", "probability", "exception", "missing"],
)
def test_invalid_attribution_returns_explicit_partial_evidence(bundle, rows, reference, problem):
    p = float(bundle.components([rows[0]])[0][0])
    candidate = reference
    mock = Mock(
        expected_value=0.0, shap_values=Mock(return_value=np.zeros((1, len(reference.names))))
    )
    if problem == "shape":
        mock.shap_values.return_value = np.zeros((len(reference.names),))
    elif problem == "nan":
        mock.shap_values.return_value = np.full((1, len(reference.names)), np.nan)
    elif problem == "base":
        mock.expected_value = np.inf
    elif problem == "exception":
        mock.shap_values.side_effect = RuntimeError("private-fixture-marker")
    elif problem == "feature_order":
        candidate = replace(reference, names=tuple(reversed(reference.names)))
    elif problem == "probability":
        p = 1 - p
    elif problem == "missing":
        candidate = None
    if problem in {"shape", "nan", "base", "additivity", "exception"}:
        candidate = replace(reference, explainer=mock)
    result = explain_supervised(bundle, rows[0], candidate, p)
    assert not result["available"] and result["top_features"] == [] and result["method"] is None
    assert "private-fixture-marker" not in str(result)


def test_schema_mismatch_refuses_reference(bundle, rows):
    other = replace(
        bundle, feature_schema={**bundle.feature_schema, "transformed_names": ["wrong"]}
    )
    with pytest.raises(ValueError):
        build_attribution(other, rows)


def test_authoritative_runtime_matches_pinned_boundary():
    runtime = require_authoritative_runtime()
    assert runtime["architecture"] == "aarch64" and runtime["libc"] == ["glibc", "2.36"]
    assert runtime["pow_probe"] == "0x1.fc10e2b044d33p-2"


@pytest.mark.parametrize(
    "mismatch", ["system", "machine", "python_version", "libc_ver", "threads", "pow"]
)
def test_unsupported_runtime_fails_closed(monkeypatch, mismatch):
    from app.ml import runtime

    if mismatch == "threads":
        monkeypatch.setenv("OMP_NUM_THREADS", "8")
    elif mismatch == "pow":
        monkeypatch.setattr(runtime.math, "pow", lambda *_: float.fromhex("0x1.fc10e2b044d32p-2"))
    else:
        monkeypatch.setattr(runtime.platform, mismatch, lambda: "unsupported")
    with pytest.raises(InvalidCSV, match="MODEL_RUNTIME_UNSUPPORTED"):
        require_authoritative_runtime()
