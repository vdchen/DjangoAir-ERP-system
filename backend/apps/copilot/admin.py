from django.contrib import admin

from .models import RebookingProposal


@admin.register(RebookingProposal)
class RebookingProposalAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "original_ticket",
        "proposed_flight",
        "fee_waived",
        "fare_difference",
        "status",
        "provider",
        "created_at",
    )
    list_filter = ("status", "fee_waived", "provider")
    search_fields = ("user__email", "original_ticket__ticket_code", "proposed_flight__flight_number")
