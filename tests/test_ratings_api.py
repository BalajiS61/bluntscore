"""User ratings: create, update, aggregate, delete, and their effect on the score."""
API = "/api/v1"


def _new_topic(client, name="Galaxy S25"):
    return client.post(f"{API}/topics", json={"name": name}).json()["slug"]


def test_create_then_update_rating(client):
    slug = _new_topic(client)
    first = client.post(f"{API}/topics/{slug}/ratings", json={"user_id": "u1", "rating": 4, "comment": "Nice"})
    assert first.status_code == 201
    assert first.json()["created"] is True
    assert first.json()["rating"]["rating"] == 4

    second = client.post(f"{API}/topics/{slug}/ratings", json={"user_id": "u1", "rating": 2})
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["rating"]["rating"] == 2

    summary = client.get(f"{API}/topics/{slug}/ratings").json()
    assert summary["count"] == 1
    assert summary["average"] == 2.0


def test_ratings_drive_the_score(client):
    slug = _new_topic(client)
    for i in range(10):
        response = client.post(f"{API}/topics/{slug}/ratings", json={"user_id": f"u{i}", "rating": 5})
    assert response.json()["topic_score"] > 50
    assert client.get(f"{API}/topics/{slug}").json()["sentiment_score"] > 50


def test_rating_aggregate(client):
    slug = _new_topic(client)
    for user, stars in [("a", 5), ("b", 4), ("c", 4), ("d", 1)]:
        client.post(f"{API}/topics/{slug}/ratings", json={"user_id": user, "rating": stars})
    body = client.get(f"{API}/topics/{slug}/ratings").json()
    assert body["count"] == 4
    assert body["average"] == 3.5
    assert body["distribution"] == {"1": 1, "2": 0, "3": 0, "4": 2, "5": 1}
    assert len(body["items"]) == 4


def test_delete_rating(client):
    slug = _new_topic(client)
    client.post(f"{API}/topics/{slug}/ratings", json={"user_id": "u1", "rating": 5})
    assert client.delete(f"{API}/topics/{slug}/ratings/u1").status_code == 204
    assert client.get(f"{API}/topics/{slug}/ratings").json()["count"] == 0
    assert client.get(f"{API}/topics/{slug}").json()["sentiment_score"] is None


def test_delete_missing_rating_is_404(client):
    slug = _new_topic(client)
    response = client.delete(f"{API}/topics/{slug}/ratings/ghost")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_rating_validation(client):
    slug = _new_topic(client)
    url = f"{API}/topics/{slug}/ratings"
    assert client.post(url, json={"user_id": "u1", "rating": 6}).status_code == 422
    assert client.post(url, json={"user_id": "u1", "rating": 0}).status_code == 422
    assert client.post(url, json={"user_id": "   ", "rating": 3}).status_code == 422
    assert client.post(url, json={"rating": 3}).status_code == 422


def test_rating_unknown_topic_is_404(client):
    response = client.post(f"{API}/topics/nope/ratings", json={"user_id": "u1", "rating": 3})
    assert response.status_code == 404
