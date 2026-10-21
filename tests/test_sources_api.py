"""Source listing and updates (with automatic rescoring)."""
API = "/api/v1"


def test_list_sources(seeded_client):
    sources = seeded_client.get(f"{API}/sources").json()
    assert [s["name"] for s in sources] == ["amazon", "reddit", "tech-news"]
    assert all(s["review_count"] > 0 for s in sources)
    tech = next(s for s in sources if s["name"] == "tech-news")
    assert tech["weight"] == 1.5 and tech["source_type"] == "news"


def test_deactivating_a_source_rescores_its_topics(seeded_client):
    response = seeded_client.patch(f"{API}/sources/tech-news", json={"is_active": False})
    assert response.status_code == 200
    body = response.json()
    assert body["source"]["is_active"] is False
    assert body["rescored_topics"] == 4

    # Pixel 9 had 7 reviews, one of them from tech-news: only 6 count now
    assert seeded_client.get(f"{API}/topics/pixel-9").json()["review_count"] == 6


def test_changing_weight_rescores(seeded_client):
    body = seeded_client.patch(f"{API}/sources/reddit", json={"weight": 2.0}).json()
    assert body["source"]["weight"] == 2.0
    assert body["rescored_topics"] == 4


def test_description_change_does_not_rescore(seeded_client):
    body = seeded_client.patch(f"{API}/sources/amazon", json={"description": "Marketplace"}).json()
    assert body["source"]["description"] == "Marketplace"
    assert body["rescored_topics"] == 0


def test_source_update_validation(seeded_client):
    assert seeded_client.patch(f"{API}/sources/amazon", json={"weight": 0}).status_code == 422
    assert seeded_client.patch(f"{API}/sources/amazon", json={"weight": 9}).status_code == 422
    assert seeded_client.patch(f"{API}/sources/amazon", json={"source_type": "tv"}).status_code == 422
    missing = seeded_client.patch(f"{API}/sources/nowhere", json={"weight": 1.0})
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"
