from django.urls import path

from .views import AirplaneListView, AirportListView, SeatTypeListView

urlpatterns = [
    path("fleet/airports/", AirportListView.as_view(), name="airport-list"),
    path("fleet/airplanes/", AirplaneListView.as_view(), name="airplane-list"),
    path("fleet/seat-types/", SeatTypeListView.as_view(), name="seat-type-list"),
]
