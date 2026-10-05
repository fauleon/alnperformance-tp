import json
import logging
import sys
from datetime import UTC, datetime

from .config import settings
from .security import redact

STANDARD = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with extras redacted (no tokens or personal data in logs)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in STANDARD}
        if extras:
            payload["extra"] = redact(extras)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)[-4000:]
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.log_level.upper())
    for noisy in ("google.ads.googleads.client", "httpx", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn, environment=settings.app_env, send_default_pii=False, traces_sample_rate=0.0
        )
