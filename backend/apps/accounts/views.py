from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserRole
from .permissions import IsSupervisor
from .serializers import (
    CustomerRegisterSerializer,
    LoginSerializer,
    StaffCreateSerializer,
    UserSerializer,
)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class StaffUserListCreateView(generics.ListCreateAPIView):
    """Supervisor endpoint to list and add Gate Managers and Check-in Managers."""

    permission_classes = [IsSupervisor]

    def get_queryset(self):
        return User.objects.filter(
            role__in=[UserRole.GATE_MANAGER, UserRole.CHECKIN_MANAGER]
        ).order_by("role", "email")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return StaffCreateSerializer
        return UserSerializer


class StaffUserDestroyView(generics.DestroyAPIView):
    """Supervisor endpoint to remove Gate Managers or Check-in Managers."""

    permission_classes = [IsSupervisor]

    def get_queryset(self):
        return User.objects.filter(role__in=[UserRole.GATE_MANAGER, UserRole.CHECKIN_MANAGER])
