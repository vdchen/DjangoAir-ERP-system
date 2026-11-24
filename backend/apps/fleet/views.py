from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Airplane, Airport, SeatType
from .serializers import AirplaneSerializer, AirportSerializer, SeatTypeSerializer


class AirportListView(generics.ListAPIView):
    queryset = Airport.objects.all()
    serializer_class = AirportSerializer
    permission_classes = [AllowAny]


class AirplaneListView(generics.ListAPIView):
    queryset = Airplane.objects.prefetch_related("seat_configs__seat_type").all()
    serializer_class = AirplaneSerializer
    permission_classes = [AllowAny]


class SeatTypeListView(generics.ListAPIView):
    queryset = SeatType.objects.all()
    serializer_class = SeatTypeSerializer
    permission_classes = [AllowAny]
