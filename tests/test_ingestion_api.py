"""Ingestion endpoints: JSON, CSV upload and sample dataset."""
JSON_URL = "/api/v1/ingest/reviews"
CSV_URL = "/api/v1/ingest/csv"
SAMPLES_URL = "/api/v1/ingest/samples"

PAYLOAD = {
    "topic": "Pixel 9",
    "source": "amazon",
    "source_type": "ecommerce",
    "reviews": [
        {"text": "Love it", "external_id": "r1"},
        {"text": "Hate the battery", "external_id": "r2"},
        {"text": "Love it"},
    ],
}


def _upload(client, content: bytes, filename="reviews.csv", topic="Pixel 9", source="amazon"):
    return client.post(
        CSV_URL,
        data={"topic": topic, "source": source, "source_type": "ecommerce"},
        files={"file": (filename, content, "text/csv")},
    )


# ---------- JSON ----------

def test_json_ingest(client):
    response = client.post(JSON_URL, json=PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["topic_slug"] == "pixel-9"
    assert body["received"] == 3
    assert body["inserted"] == 2
    assert body["duplicates"] == 1
    assert body["rejected"] == 0
    assert 0 <= body["sentiment_score"] <= 100
    assert body["verdict"]


def test_json_ingest_is_idempotent(client):
    client.post(JSON_URL, json=PAYLOAD)
    body = client.post(JSON_URL, json=PAYLOAD).json()
    assert body["inserted"] == 0
    assert body["duplicates"] == 3


def test_json_ingest_validation(client):
    assert client.post(JSON_URL, json={**PAYLOAD, "reviews": []}).status_code == 422
    assert client.post(JSON_URL, json={**PAYLOAD, "topic": "   "}).status_code == 422
    assert client.post(JSON_URL, json={**PAYLOAD, "source_type": "magazine"}).status_code == 422
    assert client.post(JSON_URL, json={**PAYLOAD, "reviews": [{"text": ""}]}).status_code == 422


# ---------- CSV ----------

def test_csv_upload(client):
    content = (
        "review,user,date\n"
        "Great phone,alice,2026-10-01\n"
        ",bob,2026-10-02\n"
        "Bad battery,carol,yesterday\n"
        "Great phone,dave,2026-10-03\n"
    ).encode("utf-8")
    response = _upload(client, content)
    assert response.status_code == 200
    body = response.json()
    assert body["received"] == 4
    assert body["inserted"] == 1
    assert body["duplicates"] == 1
    assert body["rejected"] == 2
    assert [e["row"] for e in body["errors"]] == [3, 4]


def test_csv_wrong_extension(client):
    assert _upload(client, b"text\nhello\n", filename="reviews.txt").status_code == 400


def test_csv_missing_text_column(client):
    response = _upload(client, b"name,stars\nbob,5\n")
    assert response.status_code == 400
    assert "text column" in response.json()["detail"]


def test_csv_not_utf8(client):
    assert _upload(client, "text\ncafé\n".encode("utf-16")).status_code == 400


def test_csv_header_only(client):
    assert _upload(client, b"text\n").status_code == 400


def test_csv_missing_form_fields(client):
    response = client.post(CSV_URL, files={"file": ("r.csv", b"text\nhi\n", "text/csv")})
    assert response.status_code == 422


# ---------- samples ----------

def test_load_samples_twice(client):
    first = client.post(SAMPLES_URL)
    assert first.status_code == 200
    assert len(first.json()) == 4
    assert all(t["inserted_reviews"] > 0 for t in first.json())

    second = client.post(SAMPLES_URL).json()
    assert all(t["inserted_reviews"] == 0 and t["inserted_ratings"] == 0 for t in second)
