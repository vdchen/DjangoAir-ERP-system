from django.urls import path

from .views import (
    BookingCreateView,
    BookingDetailView,
    CabinetBoardingPassPdfView,
    CabinetOnlineCheckInView,
    CabinetOverviewView,
    StaffCheckInView,
    StaffGateBoardView,
    StaffTicketDetailView,
    StaffTicketListView,
    ValidateDiscountView,
)

urlpatterns = [
    path("bookings/", BookingCreateView.as_view(), name="booking-create"),
    path("bookings/validate-discount/", ValidateDiscountView.as_view(), name="discount-validate"),
    path("bookings/<str:booking_reference>/", BookingDetailView.as_view(), name="booking-detail"),
    path("cabinet/overview/", CabinetOverviewView.as_view(), name="cabinet-overview"),
    path(
        "cabinet/tickets/<str:ticket_code>/check-in/",
        CabinetOnlineCheckInView.as_view(),
        name="cabinet-online-checkin",
    ),
    path(
        "cabinet/tickets/<str:ticket_code>/boarding-pass.pdf",
        CabinetBoardingPassPdfView.as_view(),
        name="cabinet-boarding-pass-pdf",
    ),
    path("staff/tickets/", StaffTicketListView.as_view(), name="staff-ticket-list"),
    path(
        "staff/tickets/<str:ticket_code>/",
        StaffTicketDetailView.as_view(),
        name="staff-ticket-detail",
    ),
    path("staff/checkin/", StaffCheckInView.as_view(), name="staff-checkin"),
    path("staff/gate/board/", StaffGateBoardView.as_view(), name="staff-gate-board"),
]
