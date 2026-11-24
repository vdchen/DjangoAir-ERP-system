import hashlib
import hmac
import json
import logging

import redis
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def compute_webhook_signature(secret: str, body_bytes: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def publish_domain_event(event_type: str, payload: dict) -> dict:
    """Publish a real-time event to Redis Pub/Sub (for Flask Mobile WS) and enqueue webhook delivery."""
    envelope = {
        "event": event_type,
        "timestamp": timezone.now().isoformat(),
        "data": payload,
    }

    # 1. Publish to Redis Pub/Sub for Flask Mobile WebSocket consumers
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        client.publish(settings.REDIS_EVENTS_CHANNEL, json.dumps(envelope, default=str))
    except Exception:
        logger.debug("Redis publish skipped/unavailable for event %s", event_type)

    # 2. Dispatch outbound webhooks asynchronously via Celery
    from .tasks import dispatch_webhook_event

    try:
        dispatch_webhook_event.delay(event_type, envelope)
    except Exception:
        logger.debug("Celery webhook dispatch skipped/unavailable for event %s", event_type)

    return envelope
