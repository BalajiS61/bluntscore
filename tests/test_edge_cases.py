"""Edge cases and failure paths: the parts normal usage rarely reaches."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.config import Settings
from app.db.database import get_db
from app.main import app, create_app

API = "/api/v1"


# ---------- health check when the database is down ----------

class _BrokenSession:
    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("database is down"))

    def close(self):
        pass


def test_health_reports_degraded_when_database_fails(client):
    app.dependency_overrides[get_db] = lambda: _BrokenSession()
    body = client.get(f"{API}/health").json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"


# ---------- global error handlers ----------

def _app_with_route(exc: Exception) -> TestClient:
    test_app = create_app()

    @test_app.get("/explode")
    def explode():
        raise exc

    return TestClient(test_app, raise_server_exceptions=False)


def test_unexpected_error_returns_safe_500():
    response = _app_with_route(RuntimeError("secret internal details")).get("/explode")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "code": "internal_error"}
    assert "secret" not in response.text


def test_database_conflict_returns_409():
    error = IntegrityError("INSERT ...", {}, Exception("UNIQUE constraint failed"))
    response = _app_with_route(error).get("/explode")
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


# ---------- CSV upload limits ----------

def _upload(client, content: bytes, topic="Pixel 9"):
    return client.post(
        f"{API}/ingest/csv",
        data={"topic": topic, "source": "amazon"},
        files={"file": ("reviews.csv", content, "text/csv")},
    )


def test_csv_larger_than_2mb_is_413(client):
    response = _upload(client, b"text\n" + b"a" * (2 * 1024 * 1024))
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


def test_csv_with_too_many_rows_is_400(client):
    content = ("text\n" + "".join(f"review {i}\n" for i in range(5001))).encode()
    response = _upload(client, content)
    assert response.status_code == 400
    assert "5000" in response.json()["detail"]


def test_csv_with_blank_topic_is_400(client):
    response = _upload(client, b"text\nhello\n", topic="   ")
    assert response.status_code == 400
    assert response.json()["detail"] == "Topic name cannot be empty"


# ---------- search filters ----------

def test_max_score_filter(seeded_client):
    body = seeded_client.get(f"{API}/topics", params={"max_score": 50}).json()
    assert body["total"] >= 1
    assert all(t["sentiment_score"] <= 50 for t in body["items"])


def test_sort_ascending_score_puts_unscored_topics_last(seeded_client):
    seeded_client.post(f"{API}/topics", json={"name": "Unscored Thing"})
    items = seeded_client.get(f"{API}/topics", params={"sort": "score"}).json()["items"]
    scores = [t["sentiment_score"] for t in items]
    assert scores[-1] is None
    assert scores[:-1] == sorted(scores[:-1])


# ---------- configuration validation ----------

@pytest.mark.parametrize(
    "overrides",
    [
        {"sentiment_positive_threshold": -0.5},
        {"scoring_half_life_days": 0},
        {"scoring_prior_strength": -1},
        {"scoring_rating_weight": 1.5},
    ],
)
def test_invalid_settings_are_rejected(overrides):
    with pytest.raises(ValidationError):
        Settings(**overrides)
