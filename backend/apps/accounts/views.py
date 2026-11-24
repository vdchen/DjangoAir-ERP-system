from django.conf import settings
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserRole
from .oauth import (
    authenticate_or_link_google_user,
    verify_dev_mock_google_identity,
    verify_google_id_token,
)
from .permissions import IsSupervisor
from .serializers import (
    CustomerRegisterSerializer,
    GoogleOAuthLoginSerializer,
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


class GoogleOAuthConfigView(APIView):
    """Public metadata informing the Customer SPA whether Google OAuth2 / dev mock is enabled."""

    permission_classes = [AllowAny]

    def get(self, _request):
        return Response(
            {
                "enabled": bool(
                    settings.GOOGLE_OAUTH_CLIENT_ID or settings.GOOGLE_OAUTH_DEV_MOCK_ENABLED
                ),
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "dev_mock_enabled": settings.GOOGLE_OAUTH_DEV_MOCK_ENABLED,
            }
        )


class GoogleOAuthLoginView(APIView):
    """Authenticate or link a customer via Google OAuth2 ID token (or guarded dev mock)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleOAuthLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data.get("dev_mock"):
            identity = verify_dev_mock_google_identity(
                email=data.get("email", ""),
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
            )
        elif data.get("id_token"):
            identity = verify_google_id_token(data["id_token"])
        else:
            return Response(
                {"detail": "Either id_token or dev_mock credentials are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, created = authenticate_or_link_google_user(identity)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
                "created": created,
                "linked_provider": "GOOGLE",
            },
            status=status.HTTP_200_OK,
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
