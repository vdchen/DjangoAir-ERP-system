from django.contrib import admin

from .models import Flight, Option


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_active")
    list_filter = ("category", "is_active")


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = (
        "flight_number",
        "origin",
        "destination",
        "departure_time",
        "base_price",
        "gate",
        "status",
    )
    list_filter = ("status", "origin", "destination")
    search_fields = ("flight_number",)
