import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone

from interfaces.api.main import app
from infrastructure.auth.jwt import create_token


@pytest.fixture
def client():
    return TestClient(app)


def _admin_token() -> str:
    return create_token(user_id=1, email="admin@test.com", is_admin=True)


def _user_token() -> str:
    return create_token(user_id=2, email="user@test.com", is_admin=False)


def test_admin_routes_registered():
    """All /admin routes should be registered in the app."""
    routes = {r.path for r in app.routes}
    expected = {
        "/admin/ingest",
        "/admin/assets",
        "/admin/enqueue",
        "/admin/assets/{symbol}",
    }
    assert expected.issubset(routes), f"Missing routes: {expected - routes}"


def test_admin_ingest_requires_auth(client):
    """POST /admin/ingest without token → 403 (require_admin returns 403)."""
    response = client.post("/admin/ingest")
    assert response.status_code == 403


def test_admin_ingest_forbidden_for_non_admin(client):
    """POST /admin/ingest with non-admin token → 403."""
    response = client.post(
        "/admin/ingest",
        headers={"Authorization": f"Bearer {_user_token()}"},
    )
    assert response.status_code == 403


def test_admin_create_asset_requires_auth(client):
    """POST /admin/assets without token → 403."""
    response = client.post("/admin/assets", json={})
    assert response.status_code == 403


def test_admin_enqueue_requires_auth(client):
    """POST /admin/enqueue without token → 403."""
    response = client.post("/admin/enqueue", json={"symbol": "AAPL", "asset_type": "stock"})
    assert response.status_code == 403


def test_admin_delete_asset_requires_auth(client):
    """DELETE /admin/assets/{symbol} without token → 403."""
    response = client.delete("/admin/assets/AAPL")
    assert response.status_code == 403
