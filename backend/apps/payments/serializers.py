from decimal import Decimal

from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    booking_reference = serializers.CharField(source="booking.booking_reference", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "booking_reference",
            "transaction_id",
            "provider",
            "amount",
            "currency",
            "status",
            "card_last4",
            "invoice_number",
            "failure_reason",
            "paid_at",
            "created_at",
        ]


class PaymentChargeInputSerializer(serializers.Serializer):
    booking_reference = serializers.CharField(max_length=24)
    payment_method = serializers.ChoiceField(choices=["CARD", "BALANCE"], default="CARD")
    card_number = serializers.CharField(required=False, allow_blank=True, default="")
    exp_month = serializers.IntegerField(required=False, default=12)
    exp_year = serializers.IntegerField(required=False, default=2030)
    cvv = serializers.CharField(required=False, allow_blank=True, default="")
    cardholder_name = serializers.CharField(required=False, allow_blank=True, default="")


class BalanceTopUpSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("1.00"))
    card_number = serializers.CharField()
    exp_month = serializers.IntegerField(default=12)
    exp_year = serializers.IntegerField(default=2030)
    cvv = serializers.CharField()
