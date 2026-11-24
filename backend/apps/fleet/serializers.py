from rest_framework import serializers

from .models import Airplane, AirplaneSeatConfig, Airport, SeatType


class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = ["id", "code", "name", "city", "country"]


class SeatTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeatType
        fields = ["id", "code", "name", "price_multiplier", "description"]


class AirplaneSeatConfigSerializer(serializers.ModelSerializer):
    seat_type = SeatTypeSerializer(read_only=True)

    class Meta:
        model = AirplaneSeatConfig
        fields = ["id", "seat_type", "seat_count"]


class AirplaneSerializer(serializers.ModelSerializer):
    seat_configs = AirplaneSeatConfigSerializer(many=True, read_only=True)

    class Meta:
        model = Airplane
        fields = ["id", "registration_number", "model_name", "total_capacity", "seat_configs"]
