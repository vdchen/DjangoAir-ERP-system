import json
import logging
import time

import redis
import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .events import compute_webhook_signature, compute_webhook_signature_v2
from .metrics import OUTBOX_EVENTS_TOTAL
from .models import OutboxEvent, OutboxStatus, WebhookDelivery, WebhookSubscription

logger = logging.getLogger(__name__)


@shared_task(name="integrations.dispatch_webhook_event")
def dispatch_webhook_event(event_type: str, envelope: dict) -> dict:
    subscriptions = WebhookSubscription.objects.filter(is_active=True)
    body_bytes = json.dumps(envelope, default=str, separators=(",", ":")).encode("utf-8")
    timestamp_str = str(int(time.time()))
    delivered = 0
    failed = 0

    for sub in subscriptions:
        if not sub.matches_event(event_type):
            continue
        signature = compute_webhook_signature(sub.secret, body_bytes)
        signature_v2 = compute_webhook_signature_v2(sub.secret, timestamp_str, body_bytes)
        headers = {
            "Content-Type": "application/json",
            "X-DjangoAir-Event": event_type,
            "X-DjangoAir-Timestamp": timestamp_str,
            "X-DjangoAir-Signature": signature,
            "X-DjangoAir-Signature-V2": signature_v2,
        }
        try:
            resp = requests.post(
                sub.target_url,
                data=body_bytes,
                headers=headers,
                timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
            )
            ok = 200 <= resp.status_code < 300
            WebhookDelivery.objects.create(
                subscription=sub,
                event_type=event_type,
                payload=envelope,
                response_status=resp.status_code,
                response_body=resp.text[:500],
                success=ok,
            )
            if ok:
                delivered += 1
            else:
                failed += 1
        except (requests.RequestException, OSError) as exc:
            logger.warning("Webhook delivery failed for %s: %s", sub.target_url, exc)
            WebhookDelivery.objects.create(
                subscription=sub,
                event_type=event_type,
                payload=envelope,
                response_status=None,
                response_body=str(exc)[:500],
                success=False,
            )
            failed += 1

    return {"event": event_type, "delivered": delivered, "failed": failed}


@shared_task(name="integrations.relay_outbox_event")
def relay_outbox_event(outbox_id: str) -> dict:
    """Relay a committed OutboxEvent to Redis Pub/Sub and outbound webhooks with DLQ tracking."""
    outbox = OutboxEvent.objects.filter(pk=outbox_id).first()
    if not outbox or outbox.status == OutboxStatus.PUBLISHED:
        return {"status": "skipped", "outbox_id": outbox_id}

    outbox.attempts += 1
    errors = []

    # 1. Publish to Redis Pub/Sub for Flask Mobile WebSocket subscribers
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        client.publish(settings.REDIS_EVENTS_CHANNEL, json.dumps(outbox.payload, default=str))
    except (redis.RedisError, OSError) as exc:
        logger.debug("Redis publish unavailable for outbox %s: %s", outbox.id, exc)

    # 2. Deliver to active webhook subscriptions
    wh_result = dispatch_webhook_event(outbox.event_type, outbox.payload)
    if wh_result["failed"] > 0:
        errors.append(f"{wh_result['failed']} webhook delivery failure(s)")

    if not errors:
        outbox.status = OutboxStatus.PUBLISHED
        outbox.published_at = timezone.now()
        outbox.last_error = ""
        outbox.save(update_fields=["status", "attempts", "published_at", "last_error"])
        OUTBOX_EVENTS_TOTAL.labels(event_type=outbox.event_type, status=OutboxStatus.PUBLISHED).inc()
        return {"status": "published", "outbox_id": str(outbox.id), "webhooks": wh_result}

    outbox.last_error = "; ".join(errors)
    if outbox.attempts >= outbox.max_attempts:
        outbox.status = OutboxStatus.DEAD_LETTER
        OUTBOX_EVENTS_TOTAL.labels(
            event_type=outbox.event_type, status=OutboxStatus.DEAD_LETTER
        ).inc()
    outbox.save(update_fields=["status", "attempts", "last_error"])
    return {"status": outbox.status, "outbox_id": str(outbox.id), "error": outbox.last_error}
