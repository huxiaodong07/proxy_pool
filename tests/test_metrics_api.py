from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_metrics_endpoint_exposes_prometheus_payload() -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "proxy_pool_http_requests_total" in response.text
