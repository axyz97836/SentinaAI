"""Bounded, deterministic baselines fitted exclusively on chronological training data."""

import math
import warnings
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import version
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    auc,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

from app.ingestion.validation import InvalidCSV
from app.ml.data import Row, chronological_split

SEED = 42
WEIGHTS = {"supervised": 0.60, "anomaly": 0.25, "rules": 0.15}
NUMERIC = ["log_amount", "hour_sin", "hour_cos", "weekday_sin", "weekday_cos"]
CATEGORICAL = ["currency", "country_code", "channel", "merchant_category"]
FEATURE_SCHEMA = {
    "version": "1",
    "numeric": NUMERIC,
    "categorical": CATEGORICAL,
    "excluded": ["external_id", "customer_ref", "device_ref", "fraud_label"],
    "history": "not_available",
    "amount_unit": "nominal_input_currency",
}
FloatArray = NDArray[np.float64]


def dependencies() -> dict[str, str]:
    return {
        name: version(name)
        for name in (
            "scikit-learn",
            "numpy",
            "scipy",
            "joblib",
            "threadpoolctl",
        )
    }


def features(rows: list[Row]) -> NDArray[np.object_]:
    values: list[list[float | str]] = []
    for row in rows:
        stamp = datetime.fromisoformat(row["occurred_at"])
        hour = 2 * math.pi * (stamp.hour + stamp.minute / 60) / 24
        day = 2 * math.pi * stamp.weekday() / 7
        values.append(
            [
                math.log1p(float(row["amount"])),
                math.sin(hour),
                math.cos(hour),
                math.sin(day),
                math.cos(day),
                *(row[name] for name in CATEGORICAL),
            ]
        )
    return np.asarray(values, dtype=object)


def classification_metrics(
    labels: FloatArray, probabilities: FloatArray, threshold: float
) -> dict[str, Any]:
    predictions = probabilities >= threshold
    precision, recall, _ = precision_recall_curve(labels, probabilities)
    return {
        "pr_auc": float(auc(recall, precision)),
        "average_precision": float(average_precision_score(labels, probabilities)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "confusion_matrix": confusion_matrix(labels, predictions, labels=[0, 1]).tolist(),
        "class_prevalence": float(labels.mean()),
        "decision_threshold": threshold,
        "sample_count": len(labels),
    }


@dataclass
class BaselineBundle:
    supervised: Pipeline
    anomaly: Pipeline
    reference: FloatArray
    feature_schema: dict[str, Any]
    metrics: dict[str, Any]
    provenance: dict[str, str]

    def components(self, rows: list[Row]) -> tuple[FloatArray, FloatArray]:
        matrix = features(rows)
        output = np.asarray(self.supervised.predict_proba(matrix), dtype=np.float64)
        if output.shape != (len(rows), 2) or not np.array_equal(self.supervised.classes_, [0, 1]):
            raise InvalidCSV("MODEL_OUTPUT_INVALID")
        probabilities = output[:, 1]
        scores = -np.asarray(self.anomaly.score_samples(matrix[:, : len(NUMERIC)].astype(float)))
        if scores.shape != (len(rows),) or not np.isfinite(scores).all():
            raise InvalidCSV("MODEL_OUTPUT_INVALID")
        percentiles = np.searchsorted(self.reference, scores, side="right") / len(self.reference)
        if (
            not np.isfinite(output).all()
            or not ((output >= 0) & (output <= 1)).all()
            or not np.isfinite(percentiles).all()
        ):
            raise InvalidCSV("MODEL_OUTPUT_INVALID")
        return probabilities, np.asarray(percentiles, dtype=np.float64)


def train(rows: list[Row], provenance: dict[str, str]) -> BaselineBundle:
    train_rows, validation_rows, test_rows = chronological_split(rows)
    x_train, x_validation, x_test = map(features, (train_rows, validation_rows, test_rows))
    y_train, y_validation, y_test = (
        np.asarray([int(row["fraud_label"]) for row in part], dtype=np.float64)
        for part in (train_rows, validation_rows, test_rows)
    )
    preprocessing = ColumnTransformer(
        [
            ("numeric", StandardScaler(), list(range(len(NUMERIC)))),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", max_categories=32, sparse_output=False),
                list(range(len(NUMERIC), 9)),
            ),
        ]
    )
    classifier = LogisticRegression(
        solver="lbfgs",
        max_iter=1000,
        tol=1e-8,
        class_weight="balanced",
        random_state=SEED,
    )
    supervised = Pipeline([("preprocessing", preprocessing), ("classifier", classifier)])
    anomaly = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "forest",
                IsolationForest(n_estimators=100, max_samples=256, random_state=SEED, n_jobs=1),
            ),
        ]
    )
    with threadpool_limits(limits=1), warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        try:
            supervised.fit(x_train, y_train)
            anomaly.fit(x_train[:, : len(NUMERIC)].astype(float))
        except ConvergenceWarning:
            raise InvalidCSV("MODEL_DID_NOT_CONVERGE") from None
        validation_probabilities = supervised.predict_proba(x_validation)[:, 1]
        # Select once on validation; final test is never used to fit or choose thresholds.
        threshold = max(
            (i / 100 for i in range(5, 96, 5)),
            key=lambda value: (f1_score(y_validation, validation_probabilities >= value), value),
        )
        probabilities = np.asarray(supervised.predict_proba(x_test)[:, 1], dtype=np.float64)
        reference = np.sort(-anomaly.score_samples(x_train[:, : len(NUMERIC)].astype(float)))
    schema = {**FEATURE_SCHEMA, "transformed_names": preprocessing.get_feature_names_out().tolist()}
    metrics = {
        **classification_metrics(y_test, probabilities, threshold),
        "evaluation_source": "SYNTHETIC",
        "split": "chronological_60_20_20_equal_times_together",
        "threshold_method": "validation_f1_grid_0.05_to_0.95_step_0.05_tie_highest",
        "validation": classification_metrics(y_validation, validation_probabilities, threshold),
        "split_counts": {
            name: {
                "rows": len(part),
                "positive": int(labels.sum()),
                "negative": len(part) - int(labels.sum()),
                "first_time": part[0]["occurred_at"],
                "last_time": part[-1]["occurred_at"],
            }
            for name, part, labels in zip(
                ("train", "validation", "test"),
                (train_rows, validation_rows, test_rows),
                (y_train, y_validation, y_test),
                strict=True,
            )
        },
        "configuration": {
            "seed": SEED,
            "class_weight": "balanced",
            "solver": "lbfgs",
            "max_iter": 1000,
            "tol": 1e-8,
            "trees": 100,
            "max_samples": 256,
            "max_categories": 32,
            "threads": 1,
            "weights": WEIGHTS,
        },
        "anomaly_reference": {
            "count": len(reference),
            "min": float(reference[0]),
            "max": float(reference[-1]),
            "meaning": "training_ecdf_not_probability",
        },
        "limitations": (
            "Synthetic scenario evaluation only; no real-world accuracy or calibration claim. "
            "Identifiers excluded; no historical behavior; nominal amounts are not FX converted."
        ),
    }
    return BaselineBundle(supervised, anomaly, reference, schema, metrics, provenance)
