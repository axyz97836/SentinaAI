"""The same canonical values for JSON submission, CSV scoring and replay."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ingestion.validation import row_error


class TransactionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, strict=True)
    external_id: str = Field(min_length=1, max_length=100)
    customer_ref: str = Field(min_length=1, max_length=100)
    occurred_at: str = Field(max_length=32)
    amount: str | int | float
    currency: str = Field(max_length=3)
    merchant_category: str = Field(min_length=1, max_length=80)
    country_code: str = Field(max_length=2)
    channel: str = Field(max_length=8)
    device_ref: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def canonical(self) -> "TransactionInput":
        if row_error(self.row()) is not None:
            raise ValueError("Invalid canonical transaction")
        self.amount = str(Decimal(str(self.amount)).quantize(Decimal("0.01")))
        self.occurred_at = datetime.fromisoformat(self.occurred_at).isoformat()
        self.device_ref = self.device_ref or None
        return self

    def row(self) -> dict[str, str]:
        return {key: str(value) for key, value in self.model_dump().items() if value is not None}

    def values(self) -> dict[str, Any]:
        return {
            **self.model_dump(),
            "amount": Decimal(str(self.amount)),
            "occurred_at": datetime.fromisoformat(self.occurred_at),
        }
