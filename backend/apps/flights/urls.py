from django.urls import path

from .views import (
    FlightDetailView,
    FlightSearchView,
    FlightSeatHoldView,
    FlightSeatMapView,
    StaffFlightCancelView,
    StaffFlightListCreateView,
    StaffOptionDetailView,
    StaffOptionListCreateView,
)

urlpatterns = [
    path("flights/search/", FlightSearchView.as_view(), name="flight-search"),
    path("flights/<uuid:pk>/", FlightDetailView.as_view(), name="flight-detail"),
    path("flights/<uuid:pk>/seat-map/", FlightSeatMapView.as_view(), name="flight-seat-map"),
    path("flights/<uuid:pk>/seat-holds/", FlightSeatHoldView.as_view(), name="flight-seat-holds"),
    path("staff/flights/", StaffFlightListCreateView.as_view(), name="staff-flight-list-create"),
    path("staff/flights/<uuid:pk>/cancel/", StaffFlightCancelView.as_view(), name="staff-flight-cancel"),
    path("staff/options/", StaffOptionListCreateView.as_view(), name="staff-option-list-create"),
    path("staff/options/<uuid:pk>/", StaffOptionDetailView.as_view(), name="staff-option-detail"),
]
