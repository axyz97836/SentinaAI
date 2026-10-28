"""Strict versions of the existing Phase 6 parameter shapes; no implicit defaults."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class AmountParameters(Parameters):
    multiplier: float = Field(gt=1, le=100, allow_inf_nan=False)
    min_history: int = Field(ge=1, le=100)


class VelocityParameters(Parameters):
    window_minutes: int = Field(ge=10, le=10)
    count_threshold: int = Field(ge=1, le=1000)


RuleCode = Literal["AMOUNT_OUTLIER", "HIGH_VELOCITY", "DEVICE_CHANGE"]
SCHEMAS: dict[str, type[Parameters]] = {
    "AMOUNT_OUTLIER": AmountParameters,
    "HIGH_VELOCITY": VelocityParameters,
    "DEVICE_CHANGE": Parameters,
}


def validate_parameters(code: str, values: dict[str, Any]) -> dict[str, Any]:
    if code not in SCHEMAS:
        raise ValueError("Unsupported rule code")
    return SCHEMAS[code].model_validate(values).model_dump()
