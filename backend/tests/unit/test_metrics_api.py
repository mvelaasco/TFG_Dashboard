import pytest
from fastapi.testclient import TestClient

from interfaces.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_metrics_routes_registered():
    """All /metrics routes should be registered in the app."""
    routes = {r.path for r in app.routes}
    expected = {
        "/metrics/coverage",
        "/metrics/coverage-calendar",
        "/metrics/volatility",
        "/metrics/correlations",
        "/metrics/correlation-matrix",
        "/metrics/correlate-pair",
    }
    assert expected.issubset(routes), f"Missing routes: {expected - routes}"


def test_coverage_calendar_requires_dates(client):
    """GET /metrics/coverage-calendar should fail without dates."""
    response = client.get("/metrics/coverage-calendar")
    assert response.status_code == 422


def test_volatility_requires_symbol(client):
    """GET /metrics/volatility should fail without symbol."""
    response = client.get("/metrics/volatility")
    assert response.status_code == 422


def test_correlate_pair_requires_body(client):
    """POST /metrics/correlate-pair should fail without body."""
    response = client.post("/metrics/correlate-pair")
    assert response.status_code == 422


def test_correlations_get_requires_params(client):
    """GET /metrics/correlations should fail without query params."""
    response = client.get("/metrics/correlations")
    assert response.status_code == 422


def test_correlations_post_requires_body(client):
    """POST /metrics/correlations should fail without body."""
    response = client.post("/metrics/correlations")
    assert response.status_code == 422
