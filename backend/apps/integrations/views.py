from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSupervisor

from .models import OutboxEvent, OutboxStatus, WebhookDelivery, WebhookSubscription
from .serializers import (
    OutboxEventSerializer,
    WebhookDeliverySerializer,
    WebhookSubscriptionSerializer,
)
from .tasks import relay_outbox_event


class WebhookSubscriptionListCreateView(generics.ListCreateAPIView):
    queryset = WebhookSubscription.objects.all()
    serializer_class = WebhookSubscriptionSerializer
    permission_classes = [IsSupervisor]


class WebhookSubscriptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = WebhookSubscription.objects.all()
    serializer_class = WebhookSubscriptionSerializer
    permission_classes = [IsSupervisor]


class WebhookDeliveryListView(generics.ListAPIView):
    queryset = WebhookDelivery.objects.select_related("subscription").all()[:50]
    serializer_class = WebhookDeliverySerializer
    permission_classes = [IsSupervisor]


class OutboxEventListView(generics.ListAPIView):
    serializer_class = OutboxEventSerializer
    permission_classes = [IsSupervisor]

    def get_queryset(self):
        qs = OutboxEvent.objects.all()
        status_filter = self.request.query_params.get("status", "").strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs[:50]


class OutboxEventReplayView(APIView):
    """Supervisor action to reset and replay a PENDING or DEAD_LETTER outbox event."""

    permission_classes = [IsSupervisor]

    def post(self, _request, pk):
        outbox = get_object_or_404(OutboxEvent, pk=pk)
        outbox.status = OutboxStatus.PENDING
        outbox.attempts = 0
        outbox.last_error = ""
        outbox.save(update_fields=["status", "attempts", "last_error"])
        result = relay_outbox_event(str(outbox.id))
        outbox.refresh_from_db()
        return Response(
            {"outbox": OutboxEventSerializer(outbox).data, "relay_result": result},
            status=status.HTTP_200_OK,
        )
