import logging
import time
import uuid

from config.telemetry import get_current_trace_context

from .logging_utils import request_id_var
from .metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL

logger = logging.getLogger("djangoair.http")


def _normalize_endpoint(path: str) -> str:
    """Keep Prometheus label cardinality bounded by collapsing UUID/code segments."""
    parts = [p for p in path.split("/") if p]
    normalized = []
    for part in parts:
        if len(part) == 36 and part.count("-") == 4:
            normalized.append(":id")
        elif part.startswith(("BK-", "DA-", "INV-")):
            normalized.append(":code")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized)


class RequestCorrelationAndMetricsMiddleware:
    """Propagates X-Request-ID/X-Trace-ID, logs structured request metrics, and records Prometheus telemetry."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(req_id)
        start = time.perf_counter()

        try:
            response = self.get_response(request)
        finally:
            duration = time.perf_counter() - start
            request_id_var.reset(token)

        response["X-Request-ID"] = req_id
        trace_id, _ = get_current_trace_context()
        if trace_id != "-":
            response["X-Trace-ID"] = trace_id

        endpoint = _normalize_endpoint(request.path)
        if not endpoint.endswith("/metrics"):
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=endpoint,
                status=str(response.status_code),
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(duration)

            logger.info(
                "%s %s -> %s (%.1fms)",
                request.method,
                request.path,
                response.status_code,
                duration * 1000,
            )

        return response
