import csv
from io import BytesIO, StringIO

import pytest

from app.ingestion.validation import validate_csv
from app.ml.synthetic import generate_csv


def test_deterministic_canonical_synthetic_data():
    content = generate_csv()
    assert content == generate_csv()
    assert content != generate_csv(seed=43)
    outcomes = list(validate_csv(BytesIO(content)))
    assert len(outcomes) == 2000
    assert all(code is None for _, code in outcomes)
    rows = list(csv.DictReader(StringIO(content.decode())))
    assert {row["fraud_label"] for row in rows} == {"0", "1"}
    assert 20 < sum(int(row["fraud_label"]) for row in rows) < 1000
    assert len({row["external_id"] for row in rows}) == len(rows)
    assert all(row["external_id"].startswith("synthetic-") for row in rows)
    for column in ("channel", "merchant_category", "country_code"):
        assert {row[column] for row in rows if row["fraud_label"] == "0"} == {
            row[column] for row in rows if row["fraud_label"] == "1"
        }
    assert rows == sorted(rows, key=lambda row: row["occurred_at"])


@pytest.mark.parametrize("rows", [0, 299, 10001])
def test_generator_bounds(rows):
    with pytest.raises(ValueError):
        generate_csv(rows)
