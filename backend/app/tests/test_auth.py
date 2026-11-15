import jwt

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.config import settings
from app.core.security import verify_password
from app.models import Organization, OrganizationMember, User


REGISTER_PAYLOAD = {
    "email": "Alex@Example.com",
    "password": "correct horse battery staple",
    "full_name": "Alex Morgan",
    "organization_name": "Example Team",
}


def test_register_creates_owner_workspace_and_returns_token(auth_client):
    response = auth_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "alex@example.com"
    assert "password_hash" not in body["user"]

    with auth_client.app.state.test_session() as db:
        user = db.get(User, UUID(body["user"]["id"]))
        assert user is not None
        assert user.email == "alex@example.com"
        assert verify_password(REGISTER_PAYLOAD["password"], user.password_hash)
        organization = db.query(Organization).one()
        membership = db.query(OrganizationMember).one()
        assert organization.name == "Example Team"
        assert membership.organization_id == organization.id
        assert membership.user_id == user.id
        assert membership.role == "owner"

    me = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == body["user"]["id"]


def test_registration_rejects_duplicate_email_case_insensitively(auth_client):
    first = auth_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    duplicate_payload = {**REGISTER_PAYLOAD, "email": "alex@example.com"}

    assert first.status_code == 201
    duplicate = auth_client.post("/api/v1/auth/register", json=duplicate_payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "An account with this email already exists"


def test_registration_rejects_short_password(auth_client):
    response = auth_client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "password": "short"},
    )

    assert response.status_code == 422


def test_login_and_me_reject_invalid_credentials_or_tokens(auth_client):
    auth_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    bad_login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": "incorrect password"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["detail"] == "Email or password is incorrect"

    missing_token = auth_client.get("/api/v1/auth/me")
    invalid_token = auth_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert missing_token.status_code == 401
    assert invalid_token.status_code == 401

    now = datetime.now(UTC)
    malformed_subject = jwt.encode(
        {
            "sub": [],
            "iat": now,
            "exp": now + timedelta(minutes=10),
            "iss": settings.jwt_issuer,
            "type": "access",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    malformed = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {malformed_subject}"},
    )
    assert malformed.status_code == 401


def test_login_accepts_normalized_email_and_returns_authenticated_user(auth_client):
    auth_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    response = auth_client.post(
        "/api/v1/auth/login",
        json={"email": " ALEX@example.com ", "password": REGISTER_PAYLOAD["password"]},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "alex@example.com"
