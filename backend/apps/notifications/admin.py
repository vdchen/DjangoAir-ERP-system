from django.contrib import admin

from .models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("recipient", "template_type", "subject", "status", "sent_at")
    list_filter = ("template_type", "status")
    search_fields = ("recipient", "subject")
