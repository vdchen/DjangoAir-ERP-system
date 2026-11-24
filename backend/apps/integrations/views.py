from rest_framework import generics

from apps.accounts.permissions import IsSupervisor

from .models import WebhookDelivery, WebhookSubscription
from .serializers import WebhookDeliverySerializer, WebhookSubscriptionSerializer


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
