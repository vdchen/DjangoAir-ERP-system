from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import CustomerProfile
from apps.accounts.permissions import IsCheckInManagerOrAbove, IsGateManagerOrAbove
from apps.accounts.serializers import UserSerializer

from .models import Booking, Discount, Ticket
from .serializers import (
    BookingCreateSerializer,
    BookingSerializer,
    DiscountValidateSerializer,
    StaffCheckInSerializer,
    StaffGateBoardSerializer,
    TicketSerializer,
)
from .services import create_booking, online_check_in, staff_board_passenger, staff_check_in


def _ticket_queryset():
    return Ticket.objects.select_related(
        "booking",
        "flight__origin",
        "flight__destination",
        "passenger",
        "seat_type",
    ).prefetch_related("ticket_options__option")


class BookingCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        booking = create_booking(
            flight_id=data["flight_id"],
            seat_type_id=data["seat_type_id"],
            contact_email=data["contact_email"],
            passengers_data=data["passengers"],
            option_ids=data.get("option_ids", []),
            discount_code=data.get("discount_code") or None,
            authenticated_user=request.user if request.user.is_authenticated else None,
        )
        booking = (
            Booking.objects.select_related("discount")
            .prefetch_related(
                "tickets__flight__origin",
                "tickets__flight__destination",
                "tickets__passenger",
                "tickets__seat_type",
                "tickets__ticket_options__option",
            )
            .get(pk=booking.pk)
        )
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class BookingDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, booking_reference: str):
        booking = get_object_or_404(
            Booking.objects.select_related("discount").prefetch_related(
                "tickets__flight__origin",
                "tickets__flight__destination",
                "tickets__passenger",
                "tickets__seat_type",
                "tickets__ticket_options__option",
            ),
            booking_reference__iexact=booking_reference,
        )
        return Response(BookingSerializer(booking).data)


class ValidateDiscountView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DiscountValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"].strip()
        subtotal = serializer.validated_data["subtotal"]
        try:
            discount = Discount.objects.get(code__iexact=code)
        except Discount.DoesNotExist:
            return Response(
                {"valid": False, "detail": "Promo code not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not discount.is_valid_now():
            return Response(
                {"valid": False, "detail": "Promo code is expired or inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        discount_amount = discount.calculate_discount(subtotal)
        return Response(
            {
                "valid": True,
                "code": discount.code,
                "discount_type": discount.discount_type,
                "value": str(discount.value),
                "discount_amount": str(discount_amount),
                "final_total": str(max(subtotal - discount_amount, 0)),
            }
        )


class CabinetOverviewView(APIView):
    """Customer Personal Cabinet: profile, balance, upcoming flights, and previous flights."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        now = timezone.now()
        tickets = _ticket_queryset().filter(booking__user=request.user)
        upcoming = tickets.filter(flight__departure_time__gte=now).order_by("flight__departure_time")
        previous = tickets.filter(flight__departure_time__lt=now).order_by("-flight__departure_time")
        return Response(
            {
                "user": UserSerializer(request.user).data,
                "balance": str(profile.balance),
                "upcoming_tickets": TicketSerializer(upcoming, many=True).data,
                "previous_tickets": TicketSerializer(previous, many=True).data,
            }
        )


class CabinetOnlineCheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_code: str):
        ticket = online_check_in(ticket_code=ticket_code, user=request.user)
        ticket = _ticket_queryset().get(pk=ticket.pk)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


class CabinetBoardingPassPdfView(APIView):
    """Download a printable PDF boarding pass with embedded QR code for an owned ticket."""

    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_code: str):
        from django.http import HttpResponse

        from .pdf import generate_boarding_pass_pdf

        ticket = get_object_or_404(
            _ticket_queryset(),
            ticket_code__iexact=ticket_code.strip(),
            booking__user=request.user,
        )
        pdf_bytes = generate_boarding_pass_pdf(ticket)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="boarding-pass-{ticket.ticket_code}.pdf"'
        )
        return response


class StaffTicketListView(generics.ListAPIView):
    permission_classes = [IsGateManagerOrAbove]
    serializer_class = TicketSerializer

    def get_queryset(self):
        qs = _ticket_queryset().order_by("-booking__created_at")
        q = self.request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(ticket_code__icontains=q)
                | Q(booking__booking_reference__icontains=q)
                | Q(flight__flight_number__icontains=q)
                | Q(passenger__last_name__icontains=q)
            )
        return qs[:50]


class StaffTicketDetailView(APIView):
    permission_classes = [IsGateManagerOrAbove]

    def get(self, request, ticket_code: str):
        ticket = get_object_or_404(_ticket_queryset(), ticket_code__iexact=ticket_code.strip())
        return Response(TicketSerializer(ticket).data)


class StaffCheckInView(APIView):
    """Check-in Manager (and Supervisor) action: check in passenger, add options, take luggage fee."""

    permission_classes = [IsCheckInManagerOrAbove]

    def post(self, request):
        serializer = StaffCheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ticket = staff_check_in(
            ticket_code=data["ticket_code"],
            staff_user=request.user,
            option_ids=data.get("option_ids", []),
            luggage_fee=data.get("luggage_fee", 0),
        )
        ticket = _ticket_queryset().get(pk=ticket.pk)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


class StaffGateBoardView(APIView):
    """Gate Manager (and above) action: board a checked-in passenger using ticket_code."""

    permission_classes = [IsGateManagerOrAbove]

    def post(self, request):
        serializer = StaffGateBoardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = staff_board_passenger(
            ticket_code=serializer.validated_data["ticket_code"],
            staff_user=request.user,
        )
        ticket = _ticket_queryset().get(pk=ticket.pk)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)
