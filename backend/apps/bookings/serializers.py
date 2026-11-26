from decimal import Decimal

from rest_framework import serializers

from apps.fleet.serializers import AirportSerializer, SeatTypeSerializer
from apps.flights.serializers import OptionSerializer

from .models import Booking, Discount, Passenger, Ticket, TicketOption


class PassengerInputSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=120)
    last_name = serializers.CharField(max_length=120)
    document_number = serializers.CharField(max_length=64)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    seat_number = serializers.CharField(max_length=8, required=False, allow_blank=True, allow_null=True)
    return_seat_number = serializers.CharField(
        max_length=8, required=False, allow_blank=True, allow_null=True
    )


class PassengerSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Passenger
        fields = ["id", "first_name", "last_name", "full_name", "document_number", "date_of_birth"]


class TicketOptionSerializer(serializers.ModelSerializer):
    option = OptionSerializer(read_only=True)

    class Meta:
        model = TicketOption
        fields = ["id", "option", "quantity", "unit_price", "added_stage"]


class TicketSerializer(serializers.ModelSerializer):
    passenger = PassengerSerializer(read_only=True)
    seat_type = SeatTypeSerializer(read_only=True)
    ticket_options = TicketOptionSerializer(many=True, read_only=True)
    booking_reference = serializers.CharField(source="booking.booking_reference", read_only=True)
    contact_email = serializers.EmailField(source="booking.contact_email", read_only=True)
    flight_id = serializers.UUIDField(source="flight.id", read_only=True)
    flight_number = serializers.CharField(source="flight.flight_number", read_only=True)
    flight_status = serializers.CharField(source="flight.status", read_only=True)
    gate = serializers.CharField(source="flight.gate", read_only=True)
    departure_time = serializers.DateTimeField(source="flight.departure_time", read_only=True)
    arrival_time = serializers.DateTimeField(source="flight.arrival_time", read_only=True)
    origin = AirportSerializer(source="flight.origin", read_only=True)
    destination = AirportSerializer(source="flight.destination", read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_code",
            "booking_reference",
            "contact_email",
            "flight_id",
            "flight_number",
            "flight_status",
            "origin",
            "destination",
            "departure_time",
            "arrival_time",
            "gate",
            "passenger",
            "seat_type",
            "seat_number",
            "base_fare",
            "options_total",
            "luggage_fee",
            "status",
            "checked_in_at",
            "boarded_at",
            "ticket_options",
        ]


class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discount
        fields = ["id", "code", "discount_type", "value", "valid_from", "valid_until", "is_active"]


class BookingSerializer(serializers.ModelSerializer):
    tickets = TicketSerializer(many=True, read_only=True)
    discount_code = serializers.CharField(source="discount.code", read_only=True, default=None)

    class Meta:
        model = Booking
        fields = [
            "id",
            "booking_reference",
            "contact_email",
            "discount_code",
            "subtotal_amount",
            "discount_amount",
            "total_amount",
            "status",
            "created_at",
            "tickets",
        ]


class BookingCreateSerializer(serializers.Serializer):
    flight_id = serializers.UUIDField()
    seat_type_id = serializers.UUIDField()
    return_flight_id = serializers.UUIDField(required=False, allow_null=True)
    return_seat_type_id = serializers.UUIDField(required=False, allow_null=True)
    hold_token = serializers.CharField(max_length=64, required=False, allow_blank=True, allow_null=True)
    return_hold_token = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True
    )
    contact_email = serializers.EmailField()
    passengers = PassengerInputSerializer(many=True)
    option_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    discount_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class DiscountValidateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))


class StaffCheckInSerializer(serializers.Serializer):
    ticket_code = serializers.CharField(max_length=32)
    option_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    luggage_fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=Decimal("0.00")
    )


class StaffGateBoardSerializer(serializers.Serializer):
    ticket_code = serializers.CharField(max_length=32)
