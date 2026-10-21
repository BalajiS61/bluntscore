"""Every error has the same JSON shape, and every response carries tracing headers."""
API = "/api/v1"


def test_unknown_route_uses_standard_error_shape(client):
    response = client.get("/api/v1/this/does/not/exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found", "code": "not_found"}


def test_wrong_method(client):
    response = client.delete(f"{API}/health")
    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"


def test_validation_errors_have_code_and_field_details(client):
    response = client.post(f"{API}/sentiment/analyze", json={"text": ""})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["detail"][0]["loc"] == ["body", "text"]


def test_request_id_and_timing_headers(client):
    response = client.get(f"{API}/health")
    assert len(response.headers["X-Request-ID"]) == 12
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_client_request_id_is_echoed(client):
    response = client.get(f"{API}/health", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers["X-Request-ID"] == "trace-abc-123"
