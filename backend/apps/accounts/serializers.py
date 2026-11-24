from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomerProfile, User, UserRole


class UserSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    staff_rank = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "staff_rank",
            "is_active",
            "date_joined",
            "balance",
        ]
        read_only_fields = ["id", "date_joined", "staff_rank", "balance"]

    def get_balance(self, obj: User):
        profile = getattr(obj, "customer_profile", None)
        return str(profile.balance) if profile else None


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(email=attrs["email"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled.")
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        }


class CustomerRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    phone = serializers.CharField(required=False, allow_blank=True)
    passport_number = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name", "phone", "passport_number"]

    def create(self, validated_data):
        phone = validated_data.pop("phone", "")
        passport_number = validated_data.pop("passport_number", "")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, role=UserRole.CUSTOMER, **validated_data)
        CustomerProfile.objects.update_or_create(
            user=user, defaults={"phone": phone, "passport_number": passport_number}
        )
        return user


class StaffCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.ChoiceField(
        choices=[
            (UserRole.GATE_MANAGER, "Gate Manager"),
            (UserRole.CHECKIN_MANAGER, "Check-in Manager"),
        ]
    )

    class Meta:
        model = User
        fields = ["id", "email", "password", "first_name", "last_name", "role"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, is_staff=True, **validated_data)
