from django.contrib import admin

from .models import IdempotencyRecord, OutboxEvent, WebhookDelivery, WebhookSubscription

admin.site.register(WebhookSubscription)
admin.site.register(WebhookDelivery)
admin.site.register(OutboxEvent)
admin.site.register(IdempotencyRecord)
