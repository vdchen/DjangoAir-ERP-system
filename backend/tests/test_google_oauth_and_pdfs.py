from unittest.mock import MagicMock, patch

import pytest
from django.core import mail
from django.test import override_settings

from apps.accounts.models import SocialAccount, SocialProvider, User


@pytest.mark.django_db
def test_google_oauth_config_and_dev_mock_signup_and_linking(api_client, users):
    cfg = api_client.get("/api/v1/auth/google/config/")
    assert cfg.status_code == 200
    assert cfg.data["enabled"] is True
    assert cfg.data["dev_mock_enabled"] is True

    # 1. New customer created via dev mock Google OAuth2
    resp = api_client.post(
        "/api/v1/auth/google/",
        {
            "dev_mock": True,
            "email": "oauth.new@gmail.com",
            "first_name": "Grace",
            "last_name": "Hopper",
        },
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["created"] is True
    assert resp.data["linked_provider"] == "GOOGLE"
    assert "GOOGLE" in resp.data["user"]["social_providers"]
    assert resp.data["access"]
    assert SocialAccount.objects.filter(
        provider=SocialProvider.GOOGLE, user__email="oauth.new@gmail.com"
    ).exists()

    # 2. Repeat sign-in reuses existing linked account (created=False)
    again = api_client.post(
        "/api/v1/auth/google/",
        {"dev_mock": True, "email": "oauth.new@gmail.com"},
        format="json",
    )
    assert again.status_code == 200
    assert again.data["created"] is False

    # 3. Existing email customer links seamlessly without duplicating User
    link_resp = api_client.post(
        "/api/v1/auth/google/",
        {"dev_mock": True, "email": users["customer"].email},
        format="json",
    )
    assert link_resp.status_code == 200
    assert link_resp.data["created"] is False
    assert User.objects.filter(email=users["customer"].email).count() == 1


@pytest.mark.django_db
@override_settings(GOOGLE_OAUTH_DEV_MOCK_ENABLED=False, GOOGLE_OAUTH_CLIENT_ID="test-client-id.apps.googleusercontent.com")
def test_google_oauth_real_tokeninfo_and_mock_blocked_in_prod(api_client):
    # Dev mock must be rejected when disabled
    blocked = api_client.post(
        "/api/v1/auth/google/",
        {"dev_mock": True, "email": "attacker@gmail.com"},
        format="json",
    )
    assert blocked.status_code in (401, 403)

    # Real tokeninfo verification succeeds with valid audience & verified email
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "sub": "google-uid-99999",
        "aud": "test-client-id.apps.googleusercontent.com",
        "email": "verified.user@gmail.com",
        "email_verified": "true",
        "given_name": "Linus",
        "family_name": "Torvalds",
    }
    with patch("apps.accounts.oauth.requests.get", return_value=mock_resp):
        ok = api_client.post(
            "/api/v1/auth/google/",
            {"id_token": "real-signed-google-jwt"},
            format="json",
        )
    assert ok.status_code == 200
    assert ok.data["user"]["email"] == "verified.user@gmail.com"
    assert ok.data["created"] is True

    # Audience mismatch is rejected
    bad_resp = MagicMock()
    bad_resp.status_code = 200
    bad_resp.json.return_value = {
        "sub": "google-uid-other",
        "aud": "wrong-client-id",
        "email": "bad@gmail.com",
        "email_verified": "true",
    }
    with patch("apps.accounts.oauth.requests.get", return_value=bad_resp):
        rejected = api_client.post(
            "/api/v1/auth/google/",
            {"id_token": "tampered-jwt"},
            format="json",
        )
    assert rejected.status_code == 401


@pytest.mark.django_db
def test_pdf_boarding_pass_invoice_and_email_attachments(api_client, auth_client, users, flight_setup):
    cust_client = auth_client(users["customer"])
    booking_resp = cust_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(flight_setup["flight"].id),
            "seat_type_id": str(flight_setup["eco"].id),
            "contact_email": users["customer"].email,
            "passengers": [
                {"first_name": "Jane", "last_name": "Doe", "document_number": "PDF1001"}
            ],
        },
        format="json",
    )
    assert booking_resp.status_code == 201
    ref = booking_resp.data["booking_reference"]
    ticket_code = booking_resp.data["tickets"][0]["ticket_code"]

    pay_resp = cust_client.post(
        "/api/v1/payments/charge/",
        {
            "booking_reference": ref,
            "payment_method": "CARD",
            "card_number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "424",
        },
        format="json",
    )
    assert pay_resp.status_code == 200
    payment_id = pay_resp.data["payment"]["id"]

    # Confirmation email must contain 2 PDF attachments (1 boarding pass + 1 invoice)
    assert len(mail.outbox) == 1
    attachments = mail.outbox[0].attachments
    assert len(attachments) == 2
    filenames = {a[0] for a in attachments}
    assert f"boarding-pass-{ticket_code}.pdf" in filenames
    assert any(name.startswith("invoice-") and name.endswith(".pdf") for name in filenames)
    for _, content, mimetype in attachments:
        assert mimetype == "application/pdf"
        assert content.startswith(b"%PDF-")

    # Download Boarding Pass PDF as ticket owner
    bp_resp = cust_client.get(f"/api/v1/cabinet/tickets/{ticket_code}/boarding-pass.pdf")
    assert bp_resp.status_code == 200
    assert bp_resp["Content-Type"] == "application/pdf"
    assert bp_resp.content.startswith(b"%PDF-")

    # Another user cannot download someone else's boarding pass PDF
    other_client = auth_client(users["gate"])
    denied = other_client.get(f"/api/v1/cabinet/tickets/{ticket_code}/boarding-pass.pdf")
    assert denied.status_code == 404

    # Download Invoice PDF
    inv_resp = api_client.get(f"/api/v1/payments/{payment_id}/invoice.pdf")
    assert inv_resp.status_code == 200
    assert inv_resp["Content-Type"] == "application/pdf"
    assert inv_resp.content.startswith(b"%PDF-")
