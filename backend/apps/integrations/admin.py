from django.contrib import admin

from .models import WebhookDelivery, WebhookSubscription

admin.site.register(WebhookSubscription)
admin.site.register(WebhookDelivery)
