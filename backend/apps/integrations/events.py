import hashlib
import hmac
import logging

from django.db import transaction
from django.utils import timezone

from .metrics import OUTBOX_EVENTS_TOTAL
from .models import OutboxEvent, OutboxStatus

logger = logging.getLogger(__name__)


def compute_webhook_signature(secret: str, body_bytes: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def compute_webhook_signature_v2(secret: str, timestamp: str, body_bytes: bytes) -> str:
    """Compute replay-resistant HMAC-SHA256 binding both timestamp and payload body."""
    signed_payload = f"{timestamp}.".encode() + body_bytes
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def publish_domain_event(event_type: str, payload: dict) -> dict:
    """Atomically record an OutboxEvent in PostgreSQL and relay it only after DB commit."""
    envelope = {
        "event": event_type,
        "timestamp": timezone.now().isoformat(),
        "data": payload,
    }

    outbox = OutboxEvent.objects.create(
        event_type=event_type,
        payload=envelope,
        status=OutboxStatus.PENDING,
    )
    OUTBOX_EVENTS_TOTAL.labels(event_type=event_type, status=OutboxStatus.PENDING).inc()

    from .tasks import relay_outbox_event

    def _enqueue_relay():
        try:
            relay_outbox_event.delay(str(outbox.id))
        except Exception:
            logger.debug("Celery outbox relay enqueue skipped/unavailable for %s", outbox.id)

    transaction.on_commit(_enqueue_relay)
    return envelope
