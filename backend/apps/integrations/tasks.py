import json
import logging

import requests
from celery import shared_task
from django.conf import settings

from .events import compute_webhook_signature
from .models import WebhookDelivery, WebhookSubscription

logger = logging.getLogger(__name__)


@shared_task(name="integrations.dispatch_webhook_event")
def dispatch_webhook_event(event_type: str, envelope: dict) -> dict:
    subscriptions = WebhookSubscription.objects.filter(is_active=True)
    body_bytes = json.dumps(envelope, default=str, separators=(",", ":")).encode("utf-8")
    delivered = 0
    failed = 0

    for sub in subscriptions:
        if not sub.matches_event(event_type):
            continue
        signature = compute_webhook_signature(sub.secret, body_bytes)
        headers = {
            "Content-Type": "application/json",
            "X-DjangoAir-Event": event_type,
            "X-DjangoAir-Signature": signature,
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
        except Exception as exc:
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
