import pytest
from pydantic import ValidationError

from app.auth.errors import AuthError
from app.investigations.schema import AddNote, DismissAlert, OpenCase, ResolveCase, ReviewCase
from app.investigations.views import AlertFilters, CaseFilters, parse_cursor


@pytest.mark.parametrize(
    "schema,payload",
    [
        (DismissAlert, {"reason": " "}),
        (DismissAlert, {"reason": "a" * 1001}),
        (AddNote, {"note": "\t\n"}),
        (AddNote, {"note": "a" * 2001}),
        (AddNote, {"note": "a\x00b"}),
        (AddNote, {"note": "a\x1bb"}),
        (AddNote, {"note": "\ud800"}),
        (AddNote, {"note": 123}),
        (OpenCase, {"note": ""}),
        (OpenCase, {"assigned_to": "client-controlled"}),
        (OpenCase, {"organization_id": "client-controlled"}),
        (ReviewCase, {"status": "CLOSED", "version": 1}),
        (ReviewCase, {"status": "IN_REVIEW", "version": True}),
        (ReviewCase, {"status": "IN_REVIEW", "version": "1"}),
        (ReviewCase, {"status": "IN_REVIEW", "version": 0}),
        (ReviewCase, {"status": "IN_REVIEW", "version": 2147483647}),
        (ResolveCase, {"resolution": "OTHER", "resolution_note": "demo", "version": 2}),
        (ResolveCase, {"resolution": "INCONCLUSIVE", "resolution_note": "", "version": 2}),
        (ResolveCase, {"resolution": "INCONCLUSIVE", "resolution_note": "demo"}),
        (AlertFilters, {"limit": 101}),
        (CaseFilters, {"limit": 0}),
        (AlertFilters, {"status": "CLOSED"}),
        (CaseFilters, {"status": "REOPENED"}),
        (AlertFilters, {"risk_band": "SAFE"}),
        (CaseFilters, {"date_from": "2026-01-01T00:00:00"}),
        (CaseFilters, {"date_from": "2026-01-02T00:00:00Z", "date_to": "2026-01-01T00:00:00Z"}),
    ],
)
def test_invalid_investigation_requests(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_plain_text_boundaries_and_optional_note():
    assert OpenCase().note is None
    assert AddNote(note="  Fictional\r\nreview\ttext  ").note == "Fictional\nreview\ttext"
    assert len(AddNote(note="😀" * 2000).note) == 2000
    assert len(DismissAlert(reason="a" * 1000).reason) == 1000
    assert AddNote(note="<script>fictional</script>").note == "<script>fictional</script>"


@pytest.mark.parametrize(
    "cursor", ["bad", "2026-01-01|bad", "2026-01-01T00:00:00|00000000-0000-0000-0000-000000000001"]
)
def test_cursor_refuses_malformed_or_naive_timestamp(cursor):
    with pytest.raises(AuthError, match="cursor"):
        parse_cursor(cursor)
