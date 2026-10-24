"""Bounded CSV validation. Errors contain codes and row numbers, never input."""

import csv
import re
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from io import TextIOWrapper
from typing import BinaryIO, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000
MAX_ERRORS = 100
REQUIRED = frozenset(
    {
        "external_id",
        "customer_ref",
        "occurred_at",
        "amount",
        "currency",
        "merchant_category",
        "country_code",
        "channel",
    }
)
OPTIONAL = frozenset({"device_ref", "fraud_label"})
# ISO alpha codes, not arbitrary uppercase strings. Special testing/no-currency codes excluded.
COUNTRIES = frozenset(
    """AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO
    BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK
    DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR
    GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM
    KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP
    MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL
    PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST
    SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG
    VI VN VU WF WS YE YT ZA ZM ZW""".split()
)
CURRENCIES = frozenset(
    """AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL BSD
    BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUP CVE CZK DJF DKK DOP DZD
    EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD
    IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL
    MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN
    PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN
    SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VES
    VND VUV WST XAF XAG XAU XBA XBB XBC XBD XCD XCG XDR XOF XPD XPF XPT XSU XUA YER ZAR
    ZMW ZWG""".split()
)


class InvalidCSV(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class UploadMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    purpose: Literal["TRAINING", "SCORING"]
    source_kind: Literal["SYNTHETIC", "PUBLIC_DATASET"]
    license_reference: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def provenance(self) -> "UploadMetadata":
        if self.source_kind == "PUBLIC_DATASET":
            if not self.license_reference or not self.license_reference.strip():
                raise InvalidCSV("LICENSE_REQUIRED")
            # No reviewed public samples or approval mechanism exist in the approved baseline.
            raise InvalidCSV("PUBLIC_DATASET_NOT_APPROVED")
        return self


def safe_filename(name: str) -> str:
    basename = name.replace("\\", "/").rsplit("/", 1)[-1]
    if not basename.lower().endswith(".csv") or len(basename) > 255:
        raise InvalidCSV("CSV_REQUIRED")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", basename).lstrip(".-") or "dataset.csv"


def lines(stream: TextIOWrapper) -> Iterator[str]:
    while line := stream.readline(8193):
        if len(line) > 8192:
            raise InvalidCSV("RECORD_TOO_LARGE")
        yield line


def header(reader: Iterator[list[str]]) -> list[str]:
    names = next(reader, [])
    if len(names) != len(set(names)) or not REQUIRED.issubset(names):
        raise InvalidCSV("INVALID_HEADERS")
    if set(names) - REQUIRED - OPTIONAL:
        raise InvalidCSV("UNEXPECTED_COLUMNS")
    return names


def row_error(row: dict[str, str]) -> str | None:
    for key, value in row.items():
        if (
            len(value) > (80 if key == "merchant_category" else 100)
            or any(ord(char) < 32 or ord(char) > 126 for char in value)
            or value.startswith(("=", "+", "-", "@"))
        ):
            return "UNSAFE_FIELD"
    category = row["merchant_category"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]*", category) or re.search(r"\d{7,}", category):
        return "INVALID_CATEGORY"
    for key in ("external_id", "customer_ref", "device_ref"):
        value = row.get(key, "")
        if key == "device_ref" and not value:
            continue
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
            return "INVALID_REFERENCE"
        # Reject obvious phone/card/account-like digit runs in pseudonymous fields.
        if re.search(r"\d{7,}", value):
            return "PROHIBITED_IDENTIFIER"
    stamp = row["occurred_at"]
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)", stamp):
        return "INVALID_TIMESTAMP"
    try:
        datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return "INVALID_TIMESTAMP"
    if not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", row["amount"]):
        return "INVALID_AMOUNT"
    if Decimal(row["amount"]) <= 0:
        return "INVALID_AMOUNT"
    if row["currency"] not in CURRENCIES:
        return "INVALID_CURRENCY"
    if row["country_code"] not in COUNTRIES:
        return "INVALID_COUNTRY"
    if row["channel"] not in {"WEB", "MOBILE", "POS"}:
        return "INVALID_CHANNEL"
    if "fraud_label" in row and row["fraud_label"] not in {"0", "1"}:
        return "INVALID_LABEL"
    return None


def csv_rows(
    file: BinaryIO, *, headers_only: bool = False
) -> Iterator[tuple[int, dict[str, str] | None, str | None]]:
    """Yield one outcome per data record; memory is bounded by the row/field caps."""
    file.seek(0)
    stream = TextIOWrapper(file, encoding="utf-8-sig", errors="strict", newline="")
    try:
        reader = csv.reader(lines(stream), strict=True)
        names = header(reader)
        if headers_only:
            return
        count = 0
        for count, values in enumerate(reader, 1):
            if count > MAX_ROWS:
                raise InvalidCSV("ROW_LIMIT_EXCEEDED")
            if len(values) != len(names):
                yield count, None, "INVALID_RECORD"
                continue
            row = dict(zip(names, values, strict=True))
            error = row_error(row)
            yield count, row if error is None else None, error
        if count == 0:
            raise InvalidCSV("EMPTY_DATASET")
    except UnicodeError:
        raise InvalidCSV("INVALID_ENCODING") from None
    except csv.Error:
        raise InvalidCSV("MALFORMED_CSV") from None
    finally:
        stream.detach()
        file.seek(0)


def validate_csv(file: BinaryIO, *, headers_only: bool = False) -> Iterator[tuple[int, str | None]]:
    """TRAINING keeps its unique-row contract; SCORING resolves duplicates against the DB."""
    seen: set[str] = set()
    for number, row, error in csv_rows(file, headers_only=headers_only):
        if row is not None:
            if row["external_id"] in seen:
                error = "DUPLICATE_EXTERNAL_ID"
            seen.add(row["external_id"])
        yield number, error
