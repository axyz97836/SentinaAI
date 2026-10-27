"""Bounded interventional SHAP for the verified, already-fitted supervised pipeline."""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import shap

from app.ml.data import Row, chronological_split
from app.ml.training import CATEGORICAL, NUMERIC, BaselineBundle, FloatArray, features


@dataclass(frozen=True)
class SupervisedAttribution:
    names: tuple[str, ...]
    labels: tuple[str, ...]
    mean: FloatArray
    reference_count: int
    explainer: Any


def build_attribution(bundle: BaselineBundle, rows: list[Row]) -> SupervisedAttribution:
    """Caller supplies only revalidated private TRAINING bytes with matching provenance."""
    training, _, _ = chronological_split(rows)
    expected = bundle.metrics["split_counts"]["train"]
    if (
        len(training) != expected["rows"]
        or training[0]["occurred_at"] != expected["first_time"]
        or training[-1]["occurred_at"] != expected["last_time"]
    ):
        raise ValueError("Training reference does not match the model")
    preprocessing = bundle.supervised.named_steps["preprocessing"]
    names = tuple(preprocessing.get_feature_names_out().tolist())
    if list(names) != bundle.feature_schema["transformed_names"] or not 1 <= len(names) <= 133:
        raise ValueError("Explanation feature schema is incompatible")
    matrix = np.asarray(preprocessing.transform(features(training)), dtype=np.float64)
    if matrix.shape != (len(training), len(names)) or not np.isfinite(matrix).all():
        raise ValueError("Training reference is invalid")
    mean = np.asarray(matrix.mean(axis=0), dtype=np.float64)
    labels = tuple(
        NUMERIC
        + preprocessing.named_transformers_["categorical"]
        .get_feature_names_out(CATEGORICAL)
        .tolist()
    )
    if len(labels) != len(names):
        raise ValueError("Explanation feature labels are incompatible")
    # A linear interventional explainer depends only on the true training-fold mean.
    # One mean vector is a reference representation, not a fabricated transaction.
    masker = shap.maskers.Independent(mean.reshape(1, -1), max_samples=1)
    explainer = shap.LinearExplainer(bundle.supervised.named_steps["classifier"], masker)
    return SupervisedAttribution(names, labels, mean, len(training), explainer)


def unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "method": None, "top_features": [], "reason": reason}


def explain_supervised(
    bundle: BaselineBundle,
    row: Row,
    reference: SupervisedAttribution | None,
    probability: float,
) -> dict[str, Any]:
    if reference is None:
        return unavailable("BACKGROUND_UNAVAILABLE")
    try:
        preprocessing = bundle.supervised.named_steps["preprocessing"]
        if tuple(preprocessing.get_feature_names_out().tolist()) != reference.names:
            raise ValueError("Feature order changed")
        matrix = np.asarray(preprocessing.transform(features([row])), dtype=np.float64)
        if matrix.shape != (1, len(reference.names)) or not np.isfinite(matrix).all():
            raise ValueError("Explanation input is invalid")
        values = np.asarray(reference.explainer.shap_values(matrix), dtype=np.float64)
        base = float(reference.explainer.expected_value)
        raw = np.asarray(
            bundle.supervised.named_steps["classifier"].decision_function(matrix), dtype=np.float64
        )
        if (
            values.shape != matrix.shape
            or raw.shape != (1,)
            or not np.isfinite(values).all()
            or not np.isfinite(raw).all()
            or not math.isfinite(base)
        ):
            raise ValueError("Explanation output is invalid")
        log_odds = float(raw[0])
        total = float(values.sum())
        if not math.isclose(base + total, log_odds, rel_tol=1e-10, abs_tol=1e-10):
            raise ValueError("SHAP additivity failed")
        odds = math.exp(-abs(log_odds))
        reconstructed = 1 / (1 + odds) if log_odds >= 0 else odds / (1 + odds)
        if not math.isclose(reconstructed, probability, rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError("Explanation does not describe the scored classifier output")
        contributions = values[0]
        indices = sorted(
            range(len(reference.names)), key=lambda i: (-abs(float(contributions[i])), i)
        )
        selected = [i for i in indices if contributions[i] != 0][:5]
        shown = sum(float(contributions[i]) for i in selected)
        return {
            "available": True,
            "method": "SHAP_LINEAR_INTERVENTIONAL",
            "library_version": shap.__version__,
            "component": "supervised_only",
            "units": "log_odds",
            "base_value": base,
            "model_output": log_odds,
            "all_features_contribution_sum": total,
            "remaining_features_contribution": total - shown,
            "top_features": [
                {
                    "feature": reference.labels[i],
                    "transformed_feature": reference.names[i],
                    "contribution": float(contributions[i]),
                }
                for i in selected
            ],
            "reference": "verified_training_fold_mean",
            "reference_count": reference.reference_count,
            "feature_count": len(reference.names),
            "limitation": (
                "Interventional feature independence is assumed, including one-hot features. "
                "Contributions describe this classifier's log odds, "
                "not causation or composite risk points."
            ),
        }
    except Exception:
        # Optional explanation failure cannot invent evidence or alter a valid risk score.
        return unavailable("ATTRIBUTION_UNAVAILABLE")
