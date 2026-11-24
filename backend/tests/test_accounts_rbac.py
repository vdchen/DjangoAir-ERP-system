import pytest

from apps.accounts.models import User, UserRole


@pytest.mark.django_db
def test_login_and_me_endpoint(api_client, users):
    resp = api_client.post(
        "/api/v1/auth/login/",
        {"email": "supervisor@test.local", "password": "Password123!"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["user"]["role"] == UserRole.SUPERVISOR
    token = resp.data["access"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    me = api_client.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.data["email"] == "supervisor@test.local"
    assert me.data["staff_rank"] == 3


@pytest.mark.django_db
def test_supervisor_can_add_and_remove_lower_staff_only(auth_client, users):
    sup_client = auth_client(users["supervisor"])
    gate_client = auth_client(users["gate"])
    checkin_client = auth_client(users["checkin"])

    payload = {
        "email": "new.gate@test.local",
        "password": "Password123!",
        "first_name": "Sam",
        "last_name": "Gate",
        "role": UserRole.GATE_MANAGER,
    }

    # Gate Manager and Check-in Manager cannot manage staff
    assert gate_client.post("/api/v1/staff/users/", payload, format="json").status_code == 403
    assert checkin_client.post("/api/v1/staff/users/", payload, format="json").status_code == 403

    # Supervisor can create Gate Manager and Check-in Manager
    created = sup_client.post("/api/v1/staff/users/", payload, format="json")
    assert created.status_code == 201
    new_id = created.data["id"]

    # Supervisor cannot create another Supervisor via this endpoint
    bad_role = dict(payload, email="another.sup@test.local", role=UserRole.SUPERVISOR)
    assert sup_client.post("/api/v1/staff/users/", bad_role, format="json").status_code == 400

    # Supervisor can list and delete created Gate Manager
    listed = sup_client.get("/api/v1/staff/users/")
    assert listed.status_code == 200
    emails = [u["email"] for u in listed.data]
    assert "new.gate@test.local" in emails

    deleted = sup_client.delete(f"/api/v1/staff/users/{new_id}/")
    assert deleted.status_code == 204
    assert not User.objects.filter(id=new_id).exists()
