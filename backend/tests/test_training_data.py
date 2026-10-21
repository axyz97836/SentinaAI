import csv
from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO, StringIO
from uuid import uuid4

import pytest

from app.ingestion.storage import PrivateStorage
from app.ingestion.validation import InvalidCSV
from app.ml.data import check_dataset, chronological_split, load_rows, read_rows
from app.ml.synthetic import generate_csv
from app.models import Dataset


def encode(rows):
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return BytesIO(stream.getvalue().encode())


def test_temporal_separation_and_class_counts():
    rows = read_rows(BytesIO(generate_csv()))
    train, validation, test = chronological_split(list(reversed(rows)))
    assert (len(train), len(validation), len(test)) == (1200, 400, 400)
    assert train[-1]["occurred_at"] < validation[0]["occurred_at"]
    assert validation[-1]["occurred_at"] < test[0]["occurred_at"]
    assert len({row["external_id"] for part in (train, validation, test) for row in part}) == 2000


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda rows: rows[:100], "INSUFFICIENT_SAMPLES"),
        (lambda rows: [{**row, "fraud_label": "0"} for row in rows], "INSUFFICIENT_CLASS_BALANCE"),
        (
            lambda rows: [{k: v for k, v in row.items() if k != "fraud_label"} for row in rows],
            "BINARY_LABELS_REQUIRED",
        ),
        (lambda rows: [{**row, "fraud_label": "2"} for row in rows], "INVALID_LABEL"),
        (lambda rows: rows + [rows[0]], "DUPLICATE_EXTERNAL_ID"),
        (lambda rows: [{**row, "unexpected": "value"} for row in rows], "UNEXPECTED_COLUMNS"),
    ],
)
def test_invalid_training_records(mutation, code):
    rows = read_rows(BytesIO(generate_csv()))
    with pytest.raises(InvalidCSV, match=code):
        read_rows(encode(mutation(rows)))


def test_same_time_and_one_class_holdout_rejected():
    rows = read_rows(BytesIO(generate_csv()))
    with pytest.raises(InvalidCSV, match="INSUFFICIENT_SPLIT_CLASSES"):
        chronological_split([{**row, "occurred_at": rows[0]["occurred_at"]} for row in rows])
    for row in rows[1600:]:
        row["fraud_label"] = "0"
    with pytest.raises(InvalidCSV, match="INSUFFICIENT_SPLIT_CLASSES"):
        chronological_split(rows)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("purpose", "SCORING", "VALIDATED_TRAINING_REQUIRED"),
        ("status", "UPLOADED", "VALIDATED_TRAINING_REQUIRED"),
        ("status", "REJECTED", "VALIDATED_TRAINING_REQUIRED"),
        ("schema_version", "2", "DATASET_SCHEMA_UNSUPPORTED"),
        ("object_key", "arbitrary", "DATASET_KEY_INVALID"),
        ("size_bytes", 0, "OBJECT_INTEGRITY_FAILED"),
        ("organization_id", uuid4(), "DATASET_NOT_AVAILABLE"),
        ("source_kind", "PUBLIC_DATASET", "LICENSE_REQUIRED"),
    ],
)
def test_dataset_trust_boundary(field, value, code):
    organization, identifier = uuid4(), uuid4()
    dataset = Dataset(
        id=identifier,
        organization_id=organization,
        purpose="TRAINING",
        status="VALIDATED",
        source_kind="SYNTHETIC",
        schema_version="1",
        size_bytes=100,
        object_key=PrivateStorage.key(organization, identifier),
    )
    check_dataset(dataset, organization)
    setattr(dataset, field, value)
    with pytest.raises(InvalidCSV, match=code):
        check_dataset(dataset, organization)


def test_private_loader_checks_metadata_and_preserves_original_object():
    content = generate_csv()
    organization, identifier = uuid4(), uuid4()
    dataset = Dataset(
        id=identifier,
        organization_id=organization,
        purpose="TRAINING",
        status="VALIDATED",
        source_kind="SYNTHETIC",
        schema_version="1",
        size_bytes=len(content),
        row_count=2000,
        sha256=sha256(content).hexdigest(),
        object_key=PrivateStorage.key(organization, identifier),
    )

    class Storage:
        @contextmanager
        def read(self, org, ident, size, digest):
            assert (org, ident, size, digest) == (
                organization,
                identifier,
                len(content),
                sha256(content).hexdigest(),
            )
            yield BytesIO(content)

    assert len(load_rows(dataset, organization, Storage())) == 2000
    dataset.row_count = 1999
    with pytest.raises(InvalidCSV, match="DATASET_ROW_COUNT_MISMATCH"):
        load_rows(dataset, organization, Storage())
    assert dataset.status == "VALIDATED"
