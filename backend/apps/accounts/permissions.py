from rest_framework.permissions import BasePermission

from .models import UserRole


class IsGateManagerOrAbove(BasePermission):
    message = "Gate Manager role or higher is required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.has_min_staff_role(UserRole.GATE_MANAGER))


class IsCheckInManagerOrAbove(BasePermission):
    message = "Check-in Manager role or higher is required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user and user.is_authenticated and user.has_min_staff_role(UserRole.CHECKIN_MANAGER)
        )


class IsSupervisor(BasePermission):
    message = "Supervisor role is required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.has_min_staff_role(UserRole.SUPERVISOR))
