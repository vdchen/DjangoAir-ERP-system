from django.urls import path

from .views import (
    OutboxEventListView,
    OutboxEventReplayView,
    WebhookDeliveryListView,
    WebhookSubscriptionDetailView,
    WebhookSubscriptionListCreateView,
)

urlpatterns = [
    path("integrations/webhooks/", WebhookSubscriptionListCreateView.as_view(), name="webhook-list-create"),
    path("integrations/webhooks/<uuid:pk>/", WebhookSubscriptionDetailView.as_view(), name="webhook-detail"),
    path("integrations/deliveries/", WebhookDeliveryListView.as_view(), name="webhook-delivery-list"),
    path("integrations/outbox/", OutboxEventListView.as_view(), name="outbox-list"),
    path("integrations/outbox/<uuid:pk>/replay/", OutboxEventReplayView.as_view(), name="outbox-replay"),
]
