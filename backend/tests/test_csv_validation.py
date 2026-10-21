from io import BytesIO

import pytest

from app.ingestion.validation import (
    InvalidCSV,
    UploadMetadata,
    safe_filename,
    validate_csv,
)

HEADER = (
    "external_id,customer_ref,occurred_at,amount,currency,merchant_category,country_code,channel"
)
ROW = "syn-1,customer-demo,2026-10-20T10:00:00Z,12.34,INR,grocery,IN,WEB"


def outcomes(value: str | bytes):
    return list(validate_csv(BytesIO(value.encode() if isinstance(value, str) else value)))


def test_valid_and_optional_columns():
    assert outcomes(f"{HEADER}\n{ROW}\n") == [(1, None)]
    assert outcomes(f"\ufeff{HEADER},device_ref,fraud_label\r\n{ROW},device-demo,1\r\n") == [
        (1, None)
    ]


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        ("12.34", "0", "INVALID_AMOUNT"),
        ("12.34", "NaN", "INVALID_AMOUNT"),
        ("12.34", "1e8", "INVALID_AMOUNT"),
        ("12.34", "1.001", "INVALID_AMOUNT"),
        ("12.34", "1000000000000", "INVALID_AMOUNT"),
        ("INR", "ZZZ", "INVALID_CURRENCY"),
        (",IN,", ",XX,", "INVALID_COUNTRY"),
        ("WEB", "ATM", "INVALID_CHANNEL"),
        ("2026-10-20T10:00:00Z", "2026-02-30T10:00:00Z", "INVALID_TIMESTAMP"),
        ("2026-10-20T10:00:00Z", "2026-10-20T10:00:00", "INVALID_TIMESTAMP"),
        ("2026-10-20T10:00:00Z", "2026-10-20T10:00:00+01:00", "INVALID_TIMESTAMP"),
        ("customer-demo", "fake@example.invalid", "INVALID_REFERENCE"),
        ("customer-demo", "1234567890123456", "PROHIBITED_IDENTIFIER"),
        ("customer-demo", "Demo Person", "INVALID_REFERENCE"),
        ("customer-demo", "=1+1", "UNSAFE_FIELD"),
        ("customer-demo", "@SUM(A1)", "UNSAFE_FIELD"),
        ("customer-demo", "\x00demo", "UNSAFE_FIELD"),
        ("customer-demo", "x" * 101, "UNSAFE_FIELD"),
        ("grocery", "x" * 81, "UNSAFE_FIELD"),
    ],
)
def test_bad_row_values(old, new, code):
    assert outcomes(f"{HEADER}\n{ROW.replace(old, new)}") == [(1, code)]


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ("", "INVALID_HEADERS"),
        (HEADER, "EMPTY_DATASET"),
        (HEADER.replace("external_id", "email") + "\n" + ROW, "INVALID_HEADERS"),
        (HEADER + ",external_id\n" + ROW, "INVALID_HEADERS"),
        (HEADER + ",email\n" + ROW, "UNEXPECTED_COLUMNS"),
        (HEADER + "\n" + '"unterminated', "MALFORMED_CSV"),
        (HEADER.encode() + b"\n\xff", "INVALID_ENCODING"),
        (HEADER + "\n" + "x" * 8193, "RECORD_TOO_LARGE"),
        (HEADER + "\n" + (ROW + "\n") * 10001, "ROW_LIMIT_EXCEEDED"),
    ],
)
def test_bad_documents(content, code):
    with pytest.raises(InvalidCSV, match=code):
        outcomes(content)


def test_row_counts_duplicates_and_record_width():
    assert outcomes(f"{HEADER}\n{ROW}\n{ROW}\n{ROW},extra\n") == [
        (1, None),
        (2, "DUPLICATE_EXTERNAL_ID"),
        (3, "INVALID_RECORD"),
    ]
    assert len(outcomes(HEADER + "\n" + (ROW + "\n") * 10000)) == 10000


@pytest.mark.parametrize("license_reference", [None, "", "https://example.invalid/license"])
def test_public_data_requires_independent_approval(license_reference):
    with pytest.raises(InvalidCSV, match="LICENSE_REQUIRED|PUBLIC_DATASET_NOT_APPROVED"):
        UploadMetadata(
            purpose="TRAINING", source_kind="PUBLIC_DATASET", license_reference=license_reference
        )


def test_synthetic_metadata_and_filename():
    assert UploadMetadata(purpose="SCORING", source_kind="SYNTHETIC").license_reference is None
    assert safe_filename("../../fixture.csv") == "fixture.csv"
    assert safe_filename("C:\\private\\fixture.csv") == "fixture.csv"
    assert safe_filename("=unsafe name.csv") == "_unsafe_name.csv"
    with pytest.raises(InvalidCSV):
        safe_filename("fixture.csv.exe")


def test_category_spaces_and_optional_synthetic_license():
    assert outcomes(f"{HEADER}\n{ROW.replace('grocery', 'general retail')}\n") == [(1, None)]
    metadata = UploadMetadata(purpose="TRAINING", source_kind="SYNTHETIC", license_reference="CC0")
    assert metadata.license_reference == "CC0"
