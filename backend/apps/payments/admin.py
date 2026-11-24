from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "booking", "amount", "provider", "status", "paid_at")
    list_filter = ("status", "provider")
    search_fields = ("invoice_number", "transaction_id", "booking__booking_reference")
