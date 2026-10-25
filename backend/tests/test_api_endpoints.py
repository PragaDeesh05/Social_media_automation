import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("healthy", "degraded")
    assert "services" in data


def test_auth_login():
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "lead@incubrix.com", "full_name": "Lead", "password": "IncuBrix2026!"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_brand_profiles():
    # Login
    auth_res = client.post(
        "/api/v1/auth/login",
        json={"email": "lead@incubrix.com", "full_name": "Lead", "password": "IncuBrix2026!"}
    )
    token = auth_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # List profiles
    p_res = client.get("/api/v1/brand-profiles", headers=headers)
    assert p_res.status_code == 200
    profiles = p_res.json()
    assert len(profiles) >= 1
    assert profiles[0]["brand_name"] == "IncuBrix"
