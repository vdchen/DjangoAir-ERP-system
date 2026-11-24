from unittest.mock import MagicMock, patch

import pytest

from apps.integrations.events import compute_webhook_signature
from apps.integrations.models import WebhookDelivery, WebhookSubscription
from apps.integrations.tasks import dispatch_webhook_event


@pytest.mark.django_db
def test_webhook_hmac_signature_and_delivery_audit():
    sub = WebhookSubscription.objects.create(
        name="Partner ERP",
        target_url="http://mock.local/webhook",
        secret="top-secret-key",
        events=["booking.confirmed"],
        is_active=True,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"received": true}'

    with patch("apps.integrations.tasks.requests.post", return_value=mock_resp) as mocked_post:
        result = dispatch_webhook_event(
            "booking.confirmed",
            {"event": "booking.confirmed", "data": {"booking_reference": "BK-TEST01"}},
        )

    assert result["delivered"] == 1
    assert result["failed"] == 0
    assert mocked_post.called
    call_kwargs = mocked_post.call_args.kwargs
    sent_body = call_kwargs["data"]
    sent_sig = call_kwargs["headers"]["X-DjangoAir-Signature"]
    assert sent_sig == compute_webhook_signature("top-secret-key", sent_body)

    delivery = WebhookDelivery.objects.get(subscription=sub)
    assert delivery.success is True
    assert delivery.response_status == 200
