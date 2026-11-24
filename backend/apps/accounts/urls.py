from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    GoogleOAuthConfigView,
    GoogleOAuthLoginView,
    LoginView,
    MeView,
    RegisterView,
    StaffUserDestroyView,
    StaffUserListCreateView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/google/config/", GoogleOAuthConfigView.as_view(), name="auth-google-config"),
    path("auth/google/", GoogleOAuthLoginView.as_view(), name="auth-google-login"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("staff/users/", StaffUserListCreateView.as_view(), name="staff-user-list-create"),
    path("staff/users/<uuid:pk>/", StaffUserDestroyView.as_view(), name="staff-user-destroy"),
]
