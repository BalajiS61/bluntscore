"""Topic search, details, scores, summaries and reviews."""
API = "/api/v1"


# ---------- search & list ----------

def test_list_sorted_by_score_desc(seeded_client):
    body = seeded_client.get(f"{API}/topics").json()
    assert body["total"] == 4
    scores = [t["sentiment_score"] for t in body["items"]]
    assert scores == sorted(scores, reverse=True)
    assert body["items"][0]["slug"] == "pixel-9"
    assert all(t["verdict"] for t in body["items"])


def test_search_by_name_and_category(seeded_client):
    by_name = seeded_client.get(f"{API}/topics", params={"q": "pixel"}).json()
    assert [t["slug"] for t in by_name["items"]] == ["pixel-9"]

    by_category_text = seeded_client.get(f"{API}/topics", params={"q": "smart"}).json()
    assert [t["slug"] for t in by_category_text["items"]] == ["pixel-9"]

    by_category = seeded_client.get(f"{API}/topics", params={"category": "AUDIO"}).json()
    assert [t["slug"] for t in by_category["items"]] == ["budget-earbuds-x"]


def test_search_no_match(seeded_client):
    body = seeded_client.get(f"{API}/topics", params={"q": "zzz-nothing"}).json()
    assert body["total"] == 0 and body["items"] == []


def test_score_range_filter(seeded_client):
    body = seeded_client.get(f"{API}/topics", params={"min_score": 50}).json()
    assert body["total"] >= 1
    assert all(t["sentiment_score"] >= 50 for t in body["items"])


def test_invalid_score_range_is_400(seeded_client):
    response = seeded_client.get(f"{API}/topics", params={"min_score": 80, "max_score": 20})
    assert response.status_code == 400
    assert response.json()["code"] == "bad_request"


def test_pagination(seeded_client):
    page1 = seeded_client.get(f"{API}/topics", params={"limit": 2, "offset": 0}).json()
    page2 = seeded_client.get(f"{API}/topics", params={"limit": 2, "offset": 2}).json()
    assert page1["total"] == page2["total"] == 4
    slugs = [t["slug"] for t in page1["items"] + page2["items"]]
    assert len(slugs) == len(set(slugs)) == 4


def test_sort_by_name(seeded_client):
    names = [t["name"] for t in seeded_client.get(f"{API}/topics", params={"sort": "name"}).json()["items"]]
    assert names == sorted(names)


def test_list_validation(seeded_client):
    assert seeded_client.get(f"{API}/topics", params={"limit": 0}).status_code == 422
    assert seeded_client.get(f"{API}/topics", params={"limit": 101}).status_code == 422
    assert seeded_client.get(f"{API}/topics", params={"sort": "random"}).status_code == 422
    assert seeded_client.get(f"{API}/topics", params={"min_score": 150}).status_code == 422


# ---------- create / get / delete ----------

def test_create_topic(client):
    response = client.post(f"{API}/topics", json={"name": "Galaxy S25", "category": "smartphones"})
    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "galaxy-s25"
    assert body["sentiment_score"] is None
    assert body["verdict"] == "Not enough data"


def test_create_duplicate_topic_is_409(client):
    client.post(f"{API}/topics", json={"name": "Galaxy S25"})
    response = client.post(f"{API}/topics", json={"name": "galaxy  s25"})
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


def test_create_topic_validation(client):
    assert client.post(f"{API}/topics", json={"name": "   "}).status_code == 422
    assert client.post(f"{API}/topics", json={}).status_code == 422


def test_get_topic_detail(seeded_client):
    body = seeded_client.get(f"{API}/topics/pixel-9").json()
    assert body["name"] == "Pixel 9"
    assert body["review_count"] == 7
    assert body["rating_count"] == 7
    assert body["source_count"] == 3
    assert 1 <= body["average_rating"] <= 5


def test_unknown_topic_is_404(seeded_client):
    response = seeded_client.get(f"{API}/topics/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Topic 'does-not-exist' not found", "code": "not_found"}


def test_delete_topic(seeded_client):
    assert seeded_client.delete(f"{API}/topics/pixel-9").status_code == 204
    assert seeded_client.get(f"{API}/topics/pixel-9").status_code == 404
    assert seeded_client.get(f"{API}/topics").json()["total"] == 3


# ---------- scores ----------

def test_score_breakdown(seeded_client):
    listed = next(t for t in seeded_client.get(f"{API}/topics").json()["items"] if t["slug"] == "pixel-9")
    score = seeded_client.get(f"{API}/topics/pixel-9/score").json()
    assert abs(score["score"] - listed["sentiment_score"]) < 0.2
    assert score["review_count"] == 7
    assert score["rating_count"] == 7
    assert 0 < score["reliability"] < 1
    assert score["review_score"] is not None and score["rating_score"] is not None


def test_refresh_one_topic(seeded_client):
    response = seeded_client.post(f"{API}/topics/pixel-9/score/refresh")
    assert response.status_code == 200
    assert response.json()["last_scored_at"] is not None


def test_refresh_all_topics(seeded_client):
    body = seeded_client.post(f"{API}/scores/refresh").json()
    assert body["rescored"] == 4
    assert {t["slug"] for t in body["topics"]} == {
        "pixel-9", "budget-earbuds-x", "crashyapp-2-0", "quickbite-delivery"
    }


# ---------- summary ----------

def test_summary(seeded_client):
    body = seeded_client.get(f"{API}/topics/pixel-9/summary").json()
    shares = body["sentiment"]
    assert shares["positive"]["count"] + shares["neutral"]["count"] + shares["negative"]["count"] == 7
    assert abs(sum(s["percent"] for s in shares.values()) - 100) < 0.5
    assert body["verdict"] in body["headline"]
    assert "7 reviews from 3 sources" in body["headline"]

    assert {s["source"] for s in body["by_source"]} == {"amazon", "reddit", "tech-news"}
    assert sum(s["review_count"] for s in body["by_source"]) == 7

    positives = [r["sentiment_compound"] for r in body["top_positive"]]
    assert positives == sorted(positives, reverse=True)
    assert all(r["sentiment_label"] == "positive" for r in body["top_positive"])
    assert all(r["sentiment_label"] == "negative" for r in body["top_negative"])

    ratings = body["ratings"]
    assert set(ratings["distribution"]) == {"1", "2", "3", "4", "5"}
    assert sum(ratings["distribution"].values()) == ratings["count"] == 7


def test_summary_for_empty_topic(client):
    client.post(f"{API}/topics", json={"name": "Brand New Thing"})
    body = client.get(f"{API}/topics/brand-new-thing/summary").json()
    assert body["headline"] == "No reviews yet"
    assert body["score"] is None
    assert body["sentiment"]["positive"] == {"count": 0, "percent": 0.0}
    assert body["by_source"] == []
    assert body["top_positive"] == [] and body["top_negative"] == []


# ---------- reviews ----------

def test_list_reviews_with_filters(seeded_client):
    everything = seeded_client.get(f"{API}/topics/crashyapp-2-0/reviews").json()
    assert everything["total"] == 6

    negative = seeded_client.get(f"{API}/topics/crashyapp-2-0/reviews", params={"label": "negative"}).json()
    assert negative["total"] >= 1
    assert all(r["sentiment_label"] == "negative" for r in negative["items"])

    amazon = seeded_client.get(f"{API}/topics/crashyapp-2-0/reviews", params={"source": "Amazon"}).json()
    assert amazon["total"] >= 1
    assert all(r["source"] == "amazon" for r in amazon["items"])


def test_reviews_sorted_by_compound(seeded_client):
    items = seeded_client.get(
        f"{API}/topics/pixel-9/reviews", params={"sort": "-compound", "limit": 100}
    ).json()["items"]
    values = [r["sentiment_compound"] for r in items]
    assert values == sorted(values, reverse=True)


def test_reviews_validation(seeded_client):
    assert seeded_client.get(f"{API}/topics/pixel-9/reviews", params={"label": "great"}).status_code == 422
    assert seeded_client.get(f"{API}/topics/nope/reviews").status_code == 404
