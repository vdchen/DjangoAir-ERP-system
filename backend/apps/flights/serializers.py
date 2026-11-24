from rest_framework import serializers

from apps.fleet.serializers import AirplaneSerializer, AirportSerializer

from .models import Flight, Option


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ["id", "name", "category", "price", "is_active", "description"]


class FlightListSerializer(serializers.ModelSerializer):
    origin = AirportSerializer(read_only=True)
    destination = AirportSerializer(read_only=True)
    airplane = AirplaneSerializer(read_only=True)
    seat_availability = serializers.SerializerMethodField()
    total_available_seats = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()

    class Meta:
        model = Flight
        fields = [
            "id",
            "flight_number",
            "origin",
            "destination",
            "airplane",
            "departure_time",
            "arrival_time",
            "base_price",
            "gate",
            "status",
            "seat_availability",
            "total_available_seats",
            "options",
        ]

    def get_seat_availability(self, obj: Flight):
        return obj.seat_availability()

    def get_total_available_seats(self, obj: Flight):
        return obj.total_available_seats()

    def get_options(self, obj: Flight):
        qs = obj.available_options.filter(is_active=True)
        if not qs.exists():
            qs = Option.objects.filter(is_active=True)
        return OptionSerializer(qs, many=True).data


class FlightCreateSerializer(serializers.ModelSerializer):
    available_option_ids = serializers.PrimaryKeyRelatedField(
        queryset=Option.objects.all(),
        many=True,
        required=False,
        write_only=True,
        source="available_options",
    )

    class Meta:
        model = Flight
        fields = [
            "id",
            "flight_number",
            "origin",
            "destination",
            "airplane",
            "departure_time",
            "arrival_time",
            "base_price",
            "gate",
            "status",
            "available_option_ids",
        ]
        read_only_fields = ["id", "status"]

    def validate(self, attrs):
        if attrs["origin"] == attrs["destination"]:
            raise serializers.ValidationError("Origin and destination airports must differ.")
        if attrs["arrival_time"] <= attrs["departure_time"]:
            raise serializers.ValidationError("Arrival time must be after departure time.")
        return attrs
