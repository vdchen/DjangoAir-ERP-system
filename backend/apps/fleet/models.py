import uuid
from decimal import Decimal

from django.db import models


class Airport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=120)
    country = models.CharField(max_length=120)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.city}"


class SeatType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=80)
    price_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.00"))
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["price_multiplier"]

    def __str__(self) -> str:
        return f"{self.name} (x{self.price_multiplier})"


class Airplane(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration_number = models.CharField(max_length=32, unique=True)
    model_name = models.CharField(max_length=120)
    total_capacity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["registration_number"]

    def __str__(self) -> str:
        return f"{self.model_name} ({self.registration_number})"


class AirplaneSeatConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    airplane = models.ForeignKey(Airplane, on_delete=models.CASCADE, related_name="seat_configs")
    seat_type = models.ForeignKey(SeatType, on_delete=models.PROTECT, related_name="airplane_configs")
    seat_count = models.PositiveIntegerField()

    class Meta:
        unique_together = ("airplane", "seat_type")
        ordering = ["seat_type__price_multiplier"]

    def __str__(self) -> str:
        return f"{self.airplane.registration_number} - {self.seat_type.name}: {self.seat_count}"
