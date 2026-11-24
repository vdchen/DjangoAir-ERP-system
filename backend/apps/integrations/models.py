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


class OutboxStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PUBLISHED = "PUBLISHED", "Published"
    DEAD_LETTER = "DEAD_LETTER", "Dead Letter"


class OutboxEvent(models.Model):
    """Transactional Outbox entry ensuring atomic DB commit + async event relay."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=80, db_index=True)
    payload = models.JSONField()
    status = models.CharField(
        max_length=20, choices=OutboxStatus.choices, default=OutboxStatus.PENDING, db_index=True
    )
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Outbox<{self.event_type}> [{self.status}] (attempts={self.attempts})"


class IdempotencyRecord(models.Model):
    """Stores idempotent HTTP API responses keyed by client-supplied Idempotency-Key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=128, unique=True, db_index=True)
    request_method = models.CharField(max_length=10)
    request_path = models.CharField(max_length=255)
    request_hash = models.CharField(max_length=64)
    response_status = models.PositiveIntegerField()
    response_body = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Idempotency<{self.key}> {self.request_method} {self.request_path} -> {self.response_status}"
