import uuid

from django.db import models
from django.utils import timezone


class EmailLog(models.Model):
    class Status(models.TextChoices):
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    template_type = models.CharField(max_length=64)
    body_preview = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SENT)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self) -> str:
        return f"{self.template_type} -> {self.recipient} ({self.status})"
