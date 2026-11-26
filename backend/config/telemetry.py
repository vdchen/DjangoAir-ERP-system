import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger("djangoair.telemetry")

_CONFIGURED = False


def configure_telemetry(
    service_name: str | None = None,
    *,
    instrument_django: bool = False,
    instrument_celery: bool = False,
    force: bool = False,
) -> bool:
    """Configure OpenTelemetry OTLP HTTP tracing when enabled via environment variables.

    Safe to call in all environments: if neither OTEL_TRACES_ENABLED=1 nor
    OTEL_EXPORTER_OTLP_ENDPOINT is set (and force=False), this is a clean no-op.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return True

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    enabled = os.environ.get("OTEL_TRACES_ENABLED", "0") == "1" or bool(endpoint)
    if not enabled and not force:
        return False

    svc = service_name or os.environ.get("OTEL_SERVICE_NAME", "djangoair-backend")
    app_env = os.environ.get("APP_ENV", "dev")
    resource = Resource.create(
        {
            SERVICE_NAME: svc,
            "deployment.environment": app_env,
        }
    )
    provider = TracerProvider(resource=resource)

    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        traces_endpoint = endpoint if endpoint.endswith("/v1/traces") else f"{endpoint.rstrip('/')}/v1/traces"
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_endpoint)))
        logger.info("OpenTelemetry OTLP exporter configured for %s -> %s", svc, traces_endpoint)
    else:
        logger.info("OpenTelemetry in-process TracerProvider configured for %s", svc)

    trace.set_tracer_provider(provider)

    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    if not RequestsInstrumentor().is_instrumented_by_opentelemetry:
        RequestsInstrumentor().instrument()

    if instrument_django:
        from opentelemetry.instrumentation.django import DjangoInstrumentor

        if not DjangoInstrumentor().is_instrumented_by_opentelemetry:
            DjangoInstrumentor().instrument()

    if instrument_celery:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        if not CeleryInstrumentor().is_instrumented_by_opentelemetry:
            CeleryInstrumentor().instrument()

    _CONFIGURED = True
    return True


def get_current_trace_context() -> tuple[str, str]:
    """Return (trace_id_hex, span_id_hex) for the active OpenTelemetry span, or ('-', '-')."""
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if ctx and ctx.is_valid:
        return f"{ctx.trace_id:032x}", f"{ctx.span_id:016x}"
    return "-", "-"
