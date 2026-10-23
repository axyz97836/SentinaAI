"""Revalidate private TRAINING objects before fitting anything."""

import csv
from datetime import datetime
from io import TextIOWrapper
from typing import BinaryIO
from uuid import UUID

from app.ingestion.storage import PrivateStorage
from app.ingestion.validation import MAX_BYTES, InvalidCSV, UploadMetadata, validate_csv
from app.models import Dataset

Row = dict[str, str]


def check_dataset(dataset: Dataset, organization_id: UUID) -> None:
    if dataset.organization_id != organization_id:
        raise InvalidCSV("DATASET_NOT_AVAILABLE")
    if dataset.purpose != "TRAINING" or dataset.status != "VALIDATED":
        raise InvalidCSV("VALIDATED_TRAINING_REQUIRED")
    if dataset.schema_version != "1":
        raise InvalidCSV("DATASET_SCHEMA_UNSUPPORTED")
    if dataset.object_key != PrivateStorage.key(organization_id, dataset.id):
        raise InvalidCSV("DATASET_KEY_INVALID")
    if not 0 < dataset.size_bytes <= MAX_BYTES:
        raise InvalidCSV("OBJECT_INTEGRITY_FAILED")
    UploadMetadata(
        purpose="TRAINING",
        source_kind=dataset.source_kind,
        license_reference=dataset.license_reference,
    )


def read_rows(file: BinaryIO) -> list[Row]:
    for _, code in validate_csv(file):
        if code:
            raise InvalidCSV(code)
    stream = TextIOWrapper(file, encoding="utf-8-sig", newline="")
    try:
        rows = list(csv.DictReader(stream))
    finally:
        stream.detach()
        file.seek(0)
    if any(row.get("fraud_label") not in {"0", "1"} for row in rows):
        raise InvalidCSV("BINARY_LABELS_REQUIRED")
    if len(rows) < 300:
        raise InvalidCSV("INSUFFICIENT_SAMPLES")
    positive = sum(int(row["fraud_label"]) for row in rows)
    if min(positive, len(rows) - positive) < max(30, len(rows) // 100):
        raise InvalidCSV("INSUFFICIENT_CLASS_BALANCE")
    return rows


def load_rows(dataset: Dataset, organization_id: UUID, storage: PrivateStorage) -> list[Row]:
    check_dataset(dataset, organization_id)
    with storage.read(organization_id, dataset.id, dataset.size_bytes, dataset.sha256) as file:
        rows = read_rows(file)
    if dataset.row_count != len(rows):
        raise InvalidCSV("DATASET_ROW_COUNT_MISMATCH")
    return rows


def chronological_split(rows: list[Row]) -> tuple[list[Row], list[Row], list[Row]]:
    ordered = sorted(rows, key=lambda row: datetime.fromisoformat(row["occurred_at"]))
    stamps = [datetime.fromisoformat(row["occurred_at"]) for row in ordered]
    cuts = [int(len(rows) * fraction) for fraction in (0.6, 0.8)]
    for i, cut in enumerate(cuts):
        # Keep simultaneous events together; no same-time records straddle a holdout.
        while cut < len(rows) and stamps[cut] == stamps[cut - 1]:
            cut += 1
        cuts[i] = cut
    train, validation, test = ordered[: cuts[0]], ordered[cuts[0] : cuts[1]], ordered[cuts[1] :]
    for part, minimum in ((train, 20), (validation, 5), (test, 5)):
        positive = sum(int(row["fraud_label"]) for row in part)
        if min(positive, len(part) - positive) < minimum:
            raise InvalidCSV("INSUFFICIENT_SPLIT_CLASSES")
    return train, validation, test
