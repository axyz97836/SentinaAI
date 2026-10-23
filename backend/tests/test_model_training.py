import json
from hashlib import sha256
from io import BytesIO

import numpy as np
import pytest
from sklearn.metrics import auc, average_precision_score, confusion_matrix, precision_recall_curve

from app.ingestion.validation import InvalidCSV
from app.ml.artifacts import MAGIC, pack, unpack_verified
from app.ml.data import chronological_split, read_rows
from app.ml.synthetic import generate_csv
from app.ml.training import CATEGORICAL, NUMERIC, features, train


@pytest.fixture(scope="module")
def rows():
    return read_rows(BytesIO(generate_csv()))


@pytest.fixture(scope="module")
def bundle(rows):
    return train(rows, {"fixture": "synthetic-only"})


def test_training_determinism_and_training_only_preprocessing(rows, bundle):
    again = train(rows, bundle.provenance)
    train_rows, _, test_rows = chronological_split(rows)
    probabilities, percentiles = bundle.components(test_rows)
    repeated = again.components(test_rows)
    np.testing.assert_array_equal(probabilities, repeated[0])
    np.testing.assert_array_equal(percentiles, repeated[1])
    assert bundle.metrics == again.metrics
    assert ((probabilities >= 0) & (probabilities <= 1)).all()
    assert ((percentiles >= 0) & (percentiles <= 1)).all()
    scaler = bundle.supervised.named_steps["preprocessing"].named_transformers_["numeric"]
    np.testing.assert_allclose(
        scaler.mean_, features(train_rows)[:, : len(NUMERIC)].astype(float).mean(axis=0)
    )
    assert len(bundle.reference) == len(train_rows) == 1200


def test_labels_and_identifiers_never_change_components(rows, bundle):
    altered = [
        {
            **row,
            "fraud_label": "1" if row["fraud_label"] == "0" else "0",
            "external_id": "other",
            "customer_ref": "other",
            "device_ref": "",
        }
        for row in rows
    ]
    np.testing.assert_array_equal(features(rows), features(altered))
    for before, after in zip(bundle.components(rows), bundle.components(altered), strict=True):
        np.testing.assert_array_equal(before, after)


def test_test_data_cannot_fit_models_or_choose_threshold(rows, bundle):
    changed = [dict(row) for row in rows]
    for row in changed[1600:]:
        row["amount"] = "999999999999.99"
        row["merchant_category"] = "held-out-only"
        row["fraud_label"] = str(1 - int(row["fraud_label"]))
    other = train(changed, bundle.provenance)
    assert other.metrics["decision_threshold"] == bundle.metrics["decision_threshold"]
    np.testing.assert_array_equal(other.reference, bundle.reference)
    np.testing.assert_array_equal(
        other.supervised.named_steps["classifier"].coef_,
        bundle.supervised.named_steps["classifier"].coef_,
    )
    encoder = other.supervised.named_steps["preprocessing"].named_transformers_["categorical"]
    assert "held-out-only" not in encoder.categories_[CATEGORICAL.index("merchant_category")]


def test_actual_heldout_metrics(rows, bundle):
    _, _, test_rows = chronological_split(rows)
    labels = np.asarray([int(row["fraud_label"]) for row in test_rows])
    probabilities, _ = bundle.components(test_rows)
    predictions = probabilities >= bundle.metrics["decision_threshold"]
    matrix = confusion_matrix(labels, predictions, labels=[0, 1])
    assert matrix.tolist() == bundle.metrics["confusion_matrix"]
    tn, fp, fn, tp = matrix.ravel()
    assert bundle.metrics["precision"] == tp / (tp + fp)
    assert bundle.metrics["recall"] == tp / (tp + fn)
    assert bundle.metrics["f1"] == pytest.approx(2 * tp / (2 * tp + fp + fn))
    precision, recall, _ = precision_recall_curve(labels, probabilities)
    assert bundle.metrics["pr_auc"] == auc(recall, precision)
    assert bundle.metrics["average_precision"] == average_precision_score(labels, probabilities)
    assert tn + fp + fn + tp == bundle.metrics["sample_count"] == 400


def test_numeric_anomaly_ordering_and_ecdf(rows, bundle):
    base = rows[0]
    probes = [{**base, "amount": "60.00"}, {**base, "amount": "999999999999.99"}]
    _, percentiles = bundle.components(probes)
    assert percentiles[1] > percentiles[0]
    numeric = features(probes)[:, : len(NUMERIC)].astype(float)
    scores = -bundle.anomaly.score_samples(numeric)
    np.testing.assert_array_equal(
        percentiles, [(bundle.reference <= score).mean() for score in scores]
    )


def test_bundle_roundtrip_equivalence(rows, bundle):
    content = pack(bundle)
    loaded = unpack_verified(
        content, sha256(content).hexdigest(), bundle.provenance, bundle.feature_schema
    )
    for expected, actual in zip(bundle.components(rows), loaded.components(rows), strict=True):
        np.testing.assert_array_equal(expected, actual)


@pytest.mark.parametrize(
    "problem", ["digest", "format", "schema", "provenance", "versions", "truncated"]
)
def test_unusable_artifacts_refused_before_loading(bundle, problem):
    content = pack(bundle)
    digest = sha256(content).hexdigest()
    schema, provenance = dict(bundle.feature_schema), dict(bundle.provenance)
    if problem == "digest":
        digest = "0" * 64
    elif problem == "format":
        content = b"arbitrary uploaded model"
    elif problem == "schema":
        schema["version"] = "unsupported"
    elif problem == "provenance":
        provenance["fixture"] = "foreign"
    elif problem == "versions":
        header, payload = content[len(MAGIC) :].split(b"\n", 1)
        metadata = json.loads(header)
        metadata["dependencies"]["scikit-learn"] = "unexpected"
        content = MAGIC + json.dumps(metadata).encode() + b"\n" + payload
    else:
        content = content[:-5]
    if problem != "digest":
        digest = sha256(content).hexdigest()
    with pytest.raises(InvalidCSV):
        unpack_verified(content, digest, provenance, schema)
