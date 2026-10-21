"""Consistent timestamps and documented error responses."""
API = "/api/v1"


def test_all_timestamps_are_utc_with_z_suffix(client):
    slug = client.post(f"{API}/topics", json={"name": "Galaxy S25"}).json()["slug"]
    client.post(f"{API}/topics/{slug}/ratings", json={"user_id": "u1", "rating": 5})
    updated = client.post(f"{API}/topics/{slug}/ratings", json={"user_id": "u1", "rating": 1}).json()
    assert updated["rating"]["created_at"].endswith("Z")
    assert updated["rating"]["updated_at"].endswith("Z")
    assert client.get(f"{API}/topics/{slug}").json()["created_at"].endswith("Z")


def test_error_responses_are_documented_in_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "404" in paths["/api/v1/topics/{slug}"]["get"]["responses"]
    assert "409" in paths["/api/v1/topics"]["post"]["responses"]
    assert "404" in paths["/api/v1/topics/{slug}/ratings"]["post"]["responses"]
    assert "400" in paths["/api/v1/ingest/csv"]["post"]["responses"]
