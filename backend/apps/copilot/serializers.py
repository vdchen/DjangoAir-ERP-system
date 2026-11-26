from rest_framework import serializers

from apps.bookings.serializers import BookingSerializer

from .models import RebookingProposal


class CopilotAssistInputSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=1000)
    ticket_code = serializers.CharField(
        max_length=32, required=False, allow_blank=True, allow_null=True
    )


class RebookingProposalSerializer(serializers.ModelSerializer):
    original_ticket_code = serializers.CharField(
        source="original_ticket.ticket_code", read_only=True
    )
    original_flight_number = serializers.CharField(
        source="original_ticket.flight.flight_number", read_only=True
    )
    proposed_flight_id = serializers.UUIDField(source="proposed_flight.id", read_only=True)
    proposed_flight_number = serializers.CharField(
        source="proposed_flight.flight_number", read_only=True
    )
    proposed_origin = serializers.CharField(source="proposed_flight.origin.code", read_only=True)
    proposed_destination = serializers.CharField(
        source="proposed_flight.destination.code", read_only=True
    )
    proposed_departure_time = serializers.DateTimeField(
        source="proposed_flight.departure_time", read_only=True
    )
    proposed_seat_type_name = serializers.CharField(
        source="proposed_seat_type.name", read_only=True
    )
    new_booking = BookingSerializer(read_only=True)

    class Meta:
        model = RebookingProposal
        fields = [
            "id",
            "original_ticket_code",
            "original_flight_number",
            "proposed_flight_id",
            "proposed_flight_number",
            "proposed_origin",
            "proposed_destination",
            "proposed_departure_time",
            "proposed_seat_type_name",
            "fee_waived",
            "fare_difference",
            "status",
            "provider",
            "rationale",
            "policy_citations",
            "tool_trace",
            "new_booking",
            "created_at",
            "confirmed_at",
        ]
