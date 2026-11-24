from django.contrib import admin

from .models import Booking, Discount, Passenger, Ticket, TicketOption

admin.site.register(Discount)
admin.site.register(Booking)
admin.site.register(Passenger)
admin.site.register(Ticket)
admin.site.register(TicketOption)
