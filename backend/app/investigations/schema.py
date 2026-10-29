from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

AlertStatus = Literal["NEW", "IN_CASE", "DISMISSED"]
CaseStatus = Literal["OPEN", "IN_REVIEW", "CLOSED"]
RiskBand = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def plain_text(value: str) -> str:
    value = value.replace("\r\n", "\n").strip()
    value.encode("utf-8")
    if not value or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValueError("Supply nonblank plain text without control characters")
    return value


Note = Annotated[str, Field(max_length=2000), AfterValidator(plain_text)]
Version = Annotated[int, Field(ge=1, lt=2147483647)]


class RequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class DismissAlert(RequestBody):
    reason: Annotated[str, Field(max_length=1000), AfterValidator(plain_text)]


class OpenCase(RequestBody):
    note: Note | None = None


class ReviewCase(OpenCase):
    status: Literal["IN_REVIEW"]
    version: Version


class AddNote(RequestBody):
    note: Note


class ResolveCase(RequestBody):
    resolution: Literal["CONFIRMED_FRAUD", "FALSE_POSITIVE", "INCONCLUSIVE"]
    resolution_note: Note
    version: Version
