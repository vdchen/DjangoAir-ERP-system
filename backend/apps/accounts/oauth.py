from dataclasses import dataclass

import requests
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from .models import CustomerProfile, SocialAccount, SocialProvider, User, UserRole

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


@dataclass
class GoogleIdentity:
    uid: str
    email: str
    first_name: str
    last_name: str
    picture: str = ""
    is_mock: bool = False


def verify_google_id_token(id_token: str) -> GoogleIdentity:
    """Verify a real Google OAuth2 ID token against Google's tokeninfo endpoint."""
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise ValidationError(
            {"detail": "Google OAuth2 client ID is not configured on this server."}
        )
    try:
        resp = requests.get(
            GOOGLE_TOKENINFO_URL,
            params={"id_token": id_token},
            timeout=5,
        )
    except requests.RequestException as exc:
        raise AuthenticationFailed("Unable to reach Google OAuth verification service.") from exc

    if resp.status_code != 200:
        raise AuthenticationFailed("Invalid or expired Google ID token.")

    payload = resp.json()
    if payload.get("aud") != settings.GOOGLE_OAUTH_CLIENT_ID:
        raise AuthenticationFailed("Google token audience mismatch.")
    if str(payload.get("email_verified", "")).lower() != "true":
        raise AuthenticationFailed("Google account email is not verified.")

    email = (payload.get("email") or "").strip().lower()
    uid = (payload.get("sub") or "").strip()
    if not email or not uid:
        raise AuthenticationFailed("Google token missing required identity fields.")

    return GoogleIdentity(
        uid=uid,
        email=email,
        first_name=payload.get("given_name", ""),
        last_name=payload.get("family_name", ""),
        picture=payload.get("picture", ""),
        is_mock=False,
    )


def verify_dev_mock_google_identity(
    *, email: str, first_name: str = "", last_name: str = ""
) -> GoogleIdentity:
    """Allow local development and E2E testing of Google sign-in without external OAuth secrets."""
    if not settings.GOOGLE_OAUTH_DEV_MOCK_ENABLED:
        raise AuthenticationFailed("Development Google OAuth mock is disabled in this environment.")
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        raise ValidationError({"email": "Valid email address is required for Google sign-in."})
    return GoogleIdentity(
        uid=f"mock-google-{normalized}",
        email=normalized,
        first_name=first_name.strip() or normalized.split("@")[0].title(),
        last_name=last_name.strip() or "Traveler",
        is_mock=True,
    )


@transaction.atomic
def authenticate_or_link_google_user(identity: GoogleIdentity) -> tuple[User, bool]:
    """Find an existing linked SocialAccount, link by matching email, or create a new customer."""
    existing_link = (
        SocialAccount.objects.select_related("user")
        .filter(provider=SocialProvider.GOOGLE, provider_uid=identity.uid)
        .first()
    )
    if existing_link:
        user = existing_link.user
        if not user.is_active:
            raise AuthenticationFailed("Account is disabled.")
        return user, False

    user = User.objects.filter(email=identity.email).first()
    created = False
    if not user:
        user = User.objects.create_user(
            email=identity.email,
            password=None,
            first_name=identity.first_name,
            last_name=identity.last_name,
            role=UserRole.CUSTOMER,
        )
        created = True
    else:
        if not user.is_active:
            raise AuthenticationFailed("Account is disabled.")
        if user.role == UserRole.CUSTOMER:
            CustomerProfile.objects.get_or_create(user=user)

    SocialAccount.objects.update_or_create(
        provider=SocialProvider.GOOGLE,
        provider_uid=identity.uid,
        defaults={
            "user": user,
            "extra_data": {
                "email": identity.email,
                "picture": identity.picture,
                "mock": identity.is_mock,
            },
        },
    )
    return user, created
