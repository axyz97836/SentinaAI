import json
import logging
from datetime import UTC, datetime


class SafeJSONFormatter(logging.Formatter):
    """Only explicitly approved fields are emitted; exception text is never serialized."""

    def format(self, record: logging.LogRecord) -> str:
        fields = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", "api"),
        }
        for name in (
            "action",
            "request_id",
            "job_id",
            "status",
            "elapsed_ms",
            "dependency",
            "error_code",
        ):
            if hasattr(record, name):
                fields[name] = getattr(record, name)
        return json.dumps(fields)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("sentinelai")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(SafeJSONFormatter())
        logger.addHandler(handler)
    return logger
