import uuid

from django.db import models
from django.utils import timezone


class WebhookSubscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    target_url = models.URLField(max_length=500)
    secret = models.CharField(max_length=255)
    events = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} -> {self.target_url}"

    def matches_event(self, event_type: str) -> bool:
        if not self.events or "*" in self.events:
            return True
        return event_type in self.events


class WebhookDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        WebhookSubscription, on_delete=models.CASCADE, related_name="deliveries"
    )
    event_type = models.CharField(max_length=80)
    payload = models.JSONField()
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-delivered_at"]

    def __str__(self) -> str:
        return f"{self.event_type} -> {self.subscription.name} (ok={self.success})"
