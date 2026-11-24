from django.contrib import admin

from .models import Airplane, AirplaneSeatConfig, Airport, SeatType

admin.site.register(Airport)
admin.site.register(SeatType)
admin.site.register(Airplane)
admin.site.register(AirplaneSeatConfig)
