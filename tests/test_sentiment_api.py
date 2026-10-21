"""Sentiment endpoints: responses and input validation."""
URL = "/api/v1/sentiment/analyze"
BATCH_URL = "/api/v1/sentiment/analyze/batch"


def test_analyze_positive(client):
    response = client.post(URL, json={"text": "I absolutely love this!"})
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "positive"
    assert 0 < body["compound"] <= 1
    assert 0 <= body["confidence"] <= 1
    assert set(body["scores"]) == {"positive", "neutral", "negative"}


def test_analyze_strips_whitespace(client):
    response = client.post(URL, json={"text": "   Terrible service   "})
    assert response.status_code == 200
    assert response.json()["text"] == "Terrible service"
    assert response.json()["label"] == "negative"


def test_analyze_rejects_empty_and_blank(client):
    assert client.post(URL, json={"text": ""}).status_code == 422
    assert client.post(URL, json={"text": "     "}).status_code == 422


def test_analyze_rejects_missing_field(client):
    assert client.post(URL, json={}).status_code == 422


def test_analyze_rejects_too_long(client):
    assert client.post(URL, json={"text": "a" * 5001}).status_code == 422


def test_batch_summary(client):
    response = client.post(BATCH_URL, json={"texts": ["I love it", "I hate it", "It is a phone"]})
    assert response.status_code == 200
    body = response.json()
    assert [r["label"] for r in body["results"]] == ["positive", "negative", "neutral"]
    assert body["summary"]["total"] == 3
    assert body["summary"]["positive"] == 1
    assert body["summary"]["negative"] == 1
    assert body["summary"]["neutral"] == 1


def test_batch_rejects_empty_list(client):
    assert client.post(BATCH_URL, json={"texts": []}).status_code == 422


def test_batch_rejects_more_than_100(client):
    assert client.post(BATCH_URL, json={"texts": ["ok"] * 101}).status_code == 422
