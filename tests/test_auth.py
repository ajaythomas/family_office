from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import create_access_token, decode_access_token


def test_jwt_round_trip():
    token = create_access_token("user-abc", "member")
    claims = decode_access_token(token)
    assert claims["sub"] == "user-abc"
    assert claims["role"] == "member"


def test_google_login_creates_user(client: TestClient):
    fake_claims = {"sub": "gsub-001", "email": "alice@example.com", "name": "Alice"}
    with patch("app.routers.auth.verify_google_id_token", return_value=fake_claims):
        resp = client.post("/auth/google", json={"id_token": "fake"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body


def test_google_login_is_idempotent(client: TestClient):
    fake_claims = {"sub": "gsub-002", "email": "bob@example.com", "name": "Bob"}
    with patch("app.routers.auth.verify_google_id_token", return_value=fake_claims):
        r1 = client.post("/auth/google", json={"id_token": "fake"})
        r2 = client.post("/auth/google", json={"id_token": "fake"})
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_get_me_without_token_is_unauthorized(client: TestClient):
    resp = client.get("/users/me")
    assert resp.status_code == 401


def test_get_me_with_valid_token(client: TestClient):
    fake_claims = {"sub": "gsub-003", "email": "ajay@example.com", "name": "Ajay"}
    with patch("app.routers.auth.verify_google_id_token", return_value=fake_claims):
        login = client.post("/auth/google", json={"id_token": "fake"})
    token = login.json()["access_token"]

    resp = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "ajay@example.com"
    assert data["name"] == "Ajay"
    assert data["role"] == "member"
