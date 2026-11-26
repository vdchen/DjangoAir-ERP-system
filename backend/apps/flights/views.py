from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCheckInManagerOrAbove, IsSupervisor
from apps.integrations.events import publish_domain_event
from apps.integrations.pagination import OptionalPageNumberPagination

from .models import Flight, FlightStatus, Option
from .serializers import FlightCreateSerializer, FlightListSerializer, OptionSerializer
from .services import FlightAlreadyCancelledError, cancel_flight_and_refund


class FlightSearchView(generics.ListAPIView):
    """Customer flight search by destination (code or UUID), date (YYYY-MM-DD), and passengers."""

    serializer_class = FlightListSerializer
    permission_classes = [AllowAny]
    pagination_class = OptionalPageNumberPagination

    def get_queryset(self):
        qs = (
            Flight.objects.select_related("origin", "destination", "airplane")
            .prefetch_related("airplane__seat_configs__seat_type", "available_options")
            .filter(status=FlightStatus.SCHEDULED)
        )
        destination = self.request.query_params.get("destination", "").strip()
        if destination:
            if len(destination) <= 8:
                qs = qs.filter(destination__code__iexact=destination)
            else:
                qs = qs.filter(destination__id=destination)

        date_str = self.request.query_params.get("date", "").strip()
        if date_str:
            parsed = parse_date(date_str)
            if parsed:
                qs = qs.filter(departure_time__date=parsed)

        return qs

    def list(self, request, *args, **kwargs):
        passengers = int(request.query_params.get("passengers", 1) or 1)
        queryset = Flight.attach_booked_counts(list(self.get_queryset()))
        filtered = [f for f in queryset if f.total_available_seats() >= passengers]
        default_opts = list(Option.objects.filter(is_active=True))
        page = self.paginate_queryset(filtered)
        if page is not None:
            serializer = self.get_serializer(
                page, many=True, context={"default_active_options": default_opts}
            )
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(
            filtered, many=True, context={"default_active_options": default_opts}
        )
        return Response(serializer.data)


class FlightDetailView(generics.RetrieveAPIView):
    queryset = Flight.objects.select_related("origin", "destination", "airplane").prefetch_related(
        "airplane__seat_configs__seat_type", "available_options"
    )
    serializer_class = FlightListSerializer
    permission_classes = [AllowAny]


class StaffFlightListCreateView(generics.ListCreateAPIView):
    queryset = Flight.objects.select_related("origin", "destination", "airplane").prefetch_related(
        "airplane__seat_configs__seat_type", "available_options"
    )
    pagination_class = OptionalPageNumberPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsSupervisor()]
        return [IsCheckInManagerOrAbove()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return FlightCreateSerializer
        return FlightListSerializer

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        if page is not None:
            flights = Flight.attach_booked_counts(list(page))
            default_opts = list(Option.objects.filter(is_active=True))
            serializer = self.get_serializer(
                flights, many=True, context={"default_active_options": default_opts}
            )
            return self.get_paginated_response(serializer.data)

        flights = Flight.attach_booked_counts(list(qs))
        default_opts = list(Option.objects.filter(is_active=True))
        serializer = self.get_serializer(
            flights, many=True, context={"default_active_options": default_opts}
        )
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flight = serializer.save()
        if not flight.available_options.exists():
            flight.available_options.set(Option.objects.filter(is_active=True))
        publish_domain_event(
            "flight.created",
            {
                "flight_id": str(flight.id),
                "flight_number": flight.flight_number,
                "origin": flight.origin.code,
                "destination": flight.destination.code,
                "departure_time": flight.departure_time.isoformat(),
                "gate": flight.gate,
            },
        )
        return Response(FlightListSerializer(flight).data, status=status.HTTP_201_CREATED)


class StaffFlightCancelView(APIView):
    """Supervisor action to cancel a flight, refund paid bookings to customer balance, and email passengers."""

    permission_classes = [IsSupervisor]

    def post(self, request, pk):
        try:
            result = cancel_flight_and_refund(pk)
        except FlightAlreadyCancelledError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "flight": FlightListSerializer(result.flight).data,
                "refunded_bookings": result.refunded_bookings,
            },
            status=status.HTTP_200_OK,
        )


class StaffOptionListCreateView(generics.ListCreateAPIView):
    queryset = Option.objects.all()
    serializer_class = OptionSerializer
    pagination_class = OptionalPageNumberPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsSupervisor()]
        return [IsCheckInManagerOrAbove()]


class StaffOptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Option.objects.all()
    serializer_class = OptionSerializer
    permission_classes = [IsSupervisor]
