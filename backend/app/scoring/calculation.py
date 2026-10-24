"""Reproducible decimal arithmetic at the database's six-place component precision."""

from decimal import ROUND_HALF_EVEN, Decimal

from app.ingestion.validation import InvalidCSV


def component(value: float | Decimal) -> Decimal:
    number = Decimal(str(value))
    if not number.is_finite() or not 0 <= number <= 1:
        raise InvalidCSV("MODEL_OUTPUT_INVALID")
    return number.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)


def composite(
    supervised: Decimal, anomaly: Decimal, rules: Decimal, weights: dict[str, float]
) -> int:
    if set(weights) != {"supervised", "anomaly", "rules"}:
        raise InvalidCSV("MODEL_WEIGHTS_INVALID")
    values = [Decimal(str(weights[key])) for key in ("supervised", "anomaly", "rules")]
    if any(not value.is_finite() or not 0 <= value <= 1 for value in values) or sum(values) != 1:
        raise InvalidCSV("MODEL_WEIGHTS_INVALID")
    result = 100 * sum(
        (a * b for a, b in zip((supervised, anomaly, rules), values, strict=True)), Decimal(0)
    )
    return int(result.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def band(score: int, settings: dict[str, int]) -> str:
    for name in ("critical", "high", "medium"):
        if score >= settings[f"{name}_threshold"]:
            return name.upper()
    return "LOW"
