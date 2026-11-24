from django.urls import path

from .views import (
    WebhookDeliveryListView,
    WebhookSubscriptionDetailView,
    WebhookSubscriptionListCreateView,
)

urlpatterns = [
    path("integrations/webhooks/", WebhookSubscriptionListCreateView.as_view(), name="webhook-list-create"),
    path("integrations/webhooks/<uuid:pk>/", WebhookSubscriptionDetailView.as_view(), name="webhook-detail"),
    path("integrations/deliveries/", WebhookDeliveryListView.as_view(), name="webhook-delivery-list"),
]
