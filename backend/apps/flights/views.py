from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCheckInManagerOrAbove, IsSupervisor
from apps.integrations.events import publish_domain_event
from apps.integrations.pagination import OptionalPageNumberPagination

from .models import Flight, FlightStatus, Option
from .seat_map import (
    DEFAULT_SEAT_HOLD_TTL_SECONDS,
    SeatHoldConflictError,
    get_flight_seat_map,
    hold_seats,
    release_seats,
)
from .serializers import FlightCreateSerializer, FlightListSerializer, OptionSerializer
from .services import FlightAlreadyCancelledError, cancel_flight_and_refund


def _filter_scheduled_flights(
    *, destination: str = "", origin: str = "", date_str: str = ""
):
    qs = (
        Flight.objects.select_related("origin", "destination", "airplane")
        .prefetch_related("airplane__seat_configs__seat_type", "available_options")
        .filter(status=FlightStatus.SCHEDULED)
    )
    if destination:
        if len(destination) <= 8:
            qs = qs.filter(destination__code__iexact=destination)
        else:
            qs = qs.filter(destination__id=destination)
    if origin:
        if len(origin) <= 8:
            qs = qs.filter(origin__code__iexact=origin)
        else:
            qs = qs.filter(origin__id=origin)
    if date_str:
        parsed = parse_date(date_str)
        if parsed:
            qs = qs.filter(departure_time__date=parsed)
    return qs


class FlightSearchView(generics.ListAPIView):
    """Customer flight search (one-way or round-trip when return_date is provided)."""

    serializer_class = FlightListSerializer
    permission_classes = [AllowAny]
    pagination_class = OptionalPageNumberPagination

    def get_queryset(self):
        return _filter_scheduled_flights(
            destination=self.request.query_params.get("destination", "").strip(),
            origin=self.request.query_params.get("origin", "").strip(),
            date_str=self.request.query_params.get("date", "").strip(),
        )

    def list(self, request, *args, **kwargs):
        passengers = int(request.query_params.get("passengers", 1) or 1)
        return_date = request.query_params.get("return_date", "").strip()
        origin = request.query_params.get("origin", "").strip()
        destination = request.query_params.get("destination", "").strip()

        queryset = Flight.attach_booked_counts(list(self.get_queryset()))
        filtered = [f for f in queryset if f.total_available_seats() >= passengers]
        default_opts = list(Option.objects.filter(is_active=True))

        if return_date:
            # Round-trip mode: return flights depart from outbound destination back to origin
            return_origin = destination
            return_dest = origin
            ret_qs = _filter_scheduled_flights(
                origin=return_origin,
                destination=return_dest,
                date_str=return_date,
            )
            if not return_dest and filtered:
                outbound_origins = {f.origin.code for f in filtered}
                ret_qs = ret_qs.filter(destination__code__in=outbound_origins)
            ret_flights = Flight.attach_booked_counts(list(ret_qs))
            ret_filtered = [f for f in ret_flights if f.total_available_seats() >= passengers]

            ctx = {"default_active_options": default_opts}
            return Response(
                {
                    "trip_type": "round_trip",
                    "outbound": self.get_serializer(filtered, many=True, context=ctx).data,
                    "return": self.get_serializer(ret_filtered, many=True, context=ctx).data,
                }
            )

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


class FlightSeatMapView(APIView):
    """Return interactive aircraft cabin seat grid with live occupied and Redis-held statuses."""

    permission_classes = [AllowAny]

    def get(self, request, pk):
        flight = get_object_or_404(
            Flight.objects.select_related("airplane").prefetch_related(
                "airplane__seat_configs__seat_type"
            ),
            pk=pk,
        )
        hold_token = request.query_params.get("hold_token", "").strip() or None
        return Response(get_flight_seat_map(flight, hold_token=hold_token))


class FlightSeatHoldView(APIView):
    """Place (POST) or release (DELETE) temporary Redis TTL seat holds during checkout."""

    permission_classes = [AllowAny]

    def post(self, request, pk):
        flight = get_object_or_404(
            Flight.objects.select_related("airplane").prefetch_related(
                "airplane__seat_configs__seat_type"
            ),
            pk=pk,
        )
        seat_numbers = request.data.get("seat_numbers") or []
        hold_token = request.data.get("hold_token") or None
        ttl_seconds = request.data.get("ttl_seconds", DEFAULT_SEAT_HOLD_TTL_SECONDS)
        if not isinstance(seat_numbers, list):
            return Response(
                {"detail": "seat_numbers must be a list of seat codes."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = hold_seats(
                flight=flight,
                seat_numbers=seat_numbers,
                hold_token=hold_token,
                ttl_seconds=ttl_seconds,
            )
        except SeatHoldConflictError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(result, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        seat_numbers = request.data.get("seat_numbers") or []
        hold_token = str(request.data.get("hold_token") or "").strip()
        if not hold_token or not isinstance(seat_numbers, list):
            return Response(
                {"detail": "hold_token and seat_numbers list are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = release_seats(
            flight_id=str(pk),
            seat_numbers=seat_numbers,
            hold_token=hold_token,
        )
        return Response(result, status=status.HTTP_200_OK)


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
