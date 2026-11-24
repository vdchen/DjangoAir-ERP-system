import secrets
import uuid

from django.db import models
from django.utils import timezone

from apps.bookings.models import Booking


def generate_invoice_number() -> str:
    return f"INV-{timezone.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="payments")
    transaction_id = models.CharField(max_length=64, unique=True)
    provider = models.CharField(max_length=40, default="emulated_gateway")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True
    )
    card_last4 = models.CharField(max_length=4, blank=True)
    invoice_number = models.CharField(
        max_length=40, unique=True, default=generate_invoice_number
    )
    failure_reason = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.invoice_number} ({self.status}) ${self.amount}"
