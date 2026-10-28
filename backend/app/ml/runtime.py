"""Approved numerical runtime boundary; this checks the environment, not score values."""

import json
import math
import os
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from app.ingestion.validation import InvalidCSV

PINNED = {
    "numpy": "2.3.4",
    "scipy": "1.16.3",
    "scikit-learn": "1.7.2",
    "joblib": "1.5.2",
    "threadpoolctl": "3.6.0",
    "shap": "0.54.1",
    "pandas": "3.1.0",
    "tqdm": "4.70.1",
    "slicer": "0.0.8",
    "cloudpickle": "3.1.2",
}


def require_authoritative_runtime() -> dict[str, object]:
    try:
        versions = {name: version(name) for name in PINNED}
    except PackageNotFoundError:
        raise InvalidCSV("MODEL_RUNTIME_UNSUPPORTED") from None
    threads = {
        name: os.environ.get(name)
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
    }
    # This frozen boundary detects the known libm discrepancy; no scoring math is modified.
    probe = math.pow(2.0, float.fromhex("-0x1.02d948f1ed330p+0")).hex()
    if (
        platform.system() != "Linux"
        or platform.machine() != "aarch64"
        or platform.python_version() != "3.12.15"
        or platform.libc_ver() != ("glibc", "2.36")
        or not Path("/.dockerenv").is_file()
        or versions != PINNED
        or any(value != "1" for value in threads.values())
        or probe != "0x1.fc10e2b044d33p-2"
    ):
        raise InvalidCSV("MODEL_RUNTIME_UNSUPPORTED")
    return {
        "os": "Linux",
        "architecture": "aarch64",
        "python": platform.python_version(),
        "libc": list(platform.libc_ver()),
        "versions": versions,
        "threads": threads,
        "pow_probe": probe,
    }


if __name__ == "__main__":
    print(json.dumps(require_authoritative_runtime(), sort_keys=True))
