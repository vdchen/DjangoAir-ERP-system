import contextvars
import json
import logging
from datetime import UTC, datetime

from django.conf import settings

from config.telemetry import get_current_trace_context

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JsonLogFormatter(logging.Formatter):
    """Structured single-line JSON formatter carrying APP_ENV, X-Request-ID, and OTel trace context."""

    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = get_current_trace_context()
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "env": getattr(settings, "APP_ENV", "dev"),
            "request_id": request_id_var.get(),
            "trace_id": trace_id,
            "span_id": span_id,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)
