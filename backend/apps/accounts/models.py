import uuid
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import F
from django.utils import timezone


class UserRole(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Customer"
    GATE_MANAGER = "GATE_MANAGER", "Gate Manager"
    CHECKIN_MANAGER = "CHECKIN_MANAGER", "Check-in Manager"
    SUPERVISOR = "SUPERVISOR", "Supervisor"


STAFF_ROLE_RANK = {
    UserRole.GATE_MANAGER: 1,
    UserRole.CHECKIN_MANAGER: 2,
    UserRole.SUPERVISOR: 3,
}


class UserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        role = extra_fields.get("role", UserRole.CUSTOMER)
        if role in STAFF_ROLE_RANK:
            extra_fields.setdefault("is_staff", True)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        if user.role == UserRole.CUSTOMER:
            CustomerProfile.objects.get_or_create(user=user)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("role", UserRole.SUPERVISOR)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return f"{self.email} ({self.role})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def staff_rank(self) -> int:
        if self.is_superuser:
            return STAFF_ROLE_RANK[UserRole.SUPERVISOR]
        return STAFF_ROLE_RANK.get(self.role, 0)

    def has_min_staff_role(self, min_role: str) -> bool:
        required_rank = STAFF_ROLE_RANK.get(min_role, 999)
        return self.is_active and self.staff_rank >= required_rank


class CustomerProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    phone = models.CharField(max_length=40, blank=True)
    passport_number = models.CharField(max_length=64, blank=True)

    def __str__(self) -> str:
        return f"Profile<{self.user.email}> Balance={self.balance}"

    def credit(self, amount: Decimal) -> Decimal:
        amount = Decimal(amount)
        if amount <= 0:
            raise ValueError("Credit amount must be positive.")
        CustomerProfile.objects.filter(pk=self.pk).update(balance=F("balance") + amount)
        self.refresh_from_db(fields=["balance"])
        return self.balance

    def debit(self, amount: Decimal) -> Decimal:
        amount = Decimal(amount)
        if amount <= 0:
            raise ValueError("Debit amount must be positive.")
        updated = CustomerProfile.objects.filter(pk=self.pk, balance__gte=amount).update(
            balance=F("balance") - amount
        )
        if not updated:
            raise ValueError("Insufficient customer balance.")
        self.refresh_from_db(fields=["balance"])
        return self.balance


class SocialProvider(models.TextChoices):
    GOOGLE = "GOOGLE", "Google"


class SocialAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="social_accounts")
    provider = models.CharField(max_length=32, choices=SocialProvider.choices)
    provider_uid = models.CharField(max_length=255)
    extra_data = models.JSONField(default=dict, blank=True)
    linked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("provider", "provider_uid")
        ordering = ["-linked_at"]

    def __str__(self) -> str:
        return f"{self.provider}:{self.provider_uid} -> {self.user.email}"
