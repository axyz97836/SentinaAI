"""Fictional scenarios with overlapping distributions, not real fraud ground truth."""

import argparse
import csv
import math
import random
import sys
from datetime import UTC, datetime, timedelta
from io import StringIO

from app.ingestion.validation import MAX_ROWS

COLUMNS = (
    "external_id",
    "customer_ref",
    "occurred_at",
    "amount",
    "currency",
    "merchant_category",
    "country_code",
    "channel",
    "device_ref",
    "fraud_label",
)


def generate_csv(rows: int = 2000, seed: int = 42) -> bytes:
    if not 300 <= rows <= MAX_ROWS:
        raise ValueError("Synthetic training requires 300 to 10000 rows.")
    rng = random.Random(seed)  # noqa: S311 - deterministic fictional fixtures, never secrets.
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(COLUMNS)
    # IDs and customer/device assignment are independent of labels and risk scenarios.
    identifiers = list(range(rows))
    rng.shuffle(identifiers)
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    for identifier in identifiers:
        stamp += timedelta(seconds=rng.randint(60, 1800))
        amount = min(100_000, max(0.01, rng.lognormvariate(4.2, 1.35)))
        category = rng.choice(("grocery", "travel", "electronics", "dining", "services"))
        channel = rng.choice(("WEB", "MOBILE", "POS"))
        country, currency = rng.choice((("IN", "INR"), ("US", "USD"), ("GB", "GBP")))
        # Overlap and noise prevent a single field from perfectly encoding the label.
        log_odds = (
            -3.5
            + 0.7 * (math.log1p(amount) - 4)
            + 0.8 * (category == "electronics")
            + 0.6 * (channel == "WEB")
            + 0.4 * (stamp.hour < 6)
        )
        label = int(rng.random() < 1 / (1 + math.exp(-log_odds)))
        writer.writerow(
            (
                f"synthetic-{identifier:05d}",
                f"fictional-c-{rng.randrange(80):03d}",
                stamp.isoformat().replace("+00:00", "Z"),
                f"{amount:.2f}",
                currency,
                category,
                country,
                channel,
                "" if rng.random() < 0.1 else f"fictional-d-{rng.randrange(160):03d}",
                label,
            )
        )
    return output.getvalue().encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    content = generate_csv(args.rows, args.seed)
    labels = [row["fraud_label"] for row in csv.DictReader(StringIO(content.decode()))]
    print(
        f"SYNTHETIC ONLY: rows={len(labels)} legitimate={labels.count('0')} "
        f"suspicious={labels.count('1')} seed={args.seed}",
        file=sys.stderr,
    )
    sys.stdout.buffer.write(content)


if __name__ == "__main__":
    main()
