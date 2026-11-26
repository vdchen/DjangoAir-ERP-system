from django.http import HttpResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "djangoair_http_requests_total",
    "Total HTTP requests handled by DjangoAir API",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "djangoair_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

BOOKINGS_CREATED_TOTAL = Counter(
    "djangoair_bookings_created_total",
    "Total flight bookings created",
)

PAYMENTS_TOTAL = Counter(
    "djangoair_payments_total",
    "Total payment attempts by provider and status",
    ["provider", "status"],
)

OUTBOX_EVENTS_TOTAL = Counter(
    "djangoair_outbox_events_total",
    "Transactional outbox events by event type and final status",
    ["event_type", "status"],
)


def metrics_view(_request):
    """Expose Prometheus metrics in standard text exposition format."""
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
