from rest_framework import serializers

from .models import WebhookDelivery, WebhookSubscription


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookSubscription
        fields = ["id", "name", "target_url", "secret", "events", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class WebhookDeliverySerializer(serializers.ModelSerializer):
    subscription_name = serializers.CharField(source="subscription.name", read_only=True)

    class Meta:
        model = WebhookDelivery
        fields = [
            "id",
            "subscription",
            "subscription_name",
            "event_type",
            "payload",
            "response_status",
            "response_body",
            "success",
            "delivered_at",
        ]
