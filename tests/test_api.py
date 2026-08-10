import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("YOUTUBE_API_KEY", "test-youtube-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

from app.main import app
from app.models import AntiRecommendationResponse, ContrastDimension, SearchConcept, SearchResultItem, SourceVideo


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "YouTube Anti-Recommender" in response.text


def test_api_success(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    def fake_generate(self, request):
        return AntiRecommendationResponse(
            source_video=SourceVideo(
                video_id="dQw4w9WgXcQ",
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                title="Source",
                description="",
                channel_id="channel",
                channel_title="Channel",
                tags=[],
            ),
            source_interpretation="Reading",
            concepts=[
                SearchConcept(
                    query="repair tutorial",
                    contrast_dimension=ContrastDimension.ACTIVITY,
                    rationale="Hands-on",
                ),
                SearchConcept(
                    query="slow documentary",
                    contrast_dimension=ContrastDimension.FORMAT,
                    rationale="Long-form",
                ),
                SearchConcept(
                    query="budget alternatives",
                    contrast_dimension=ContrastDimension.CONSUMPTION,
                    rationale="Frugal",
                ),
            ],
            recommendations=[
                SearchResultItem(
                    video_id="abc12345678",
                    url="https://www.youtube.com/watch?v=abc12345678",
                    title="Result",
                    description="",
                    thumbnail_url=None,
                    channel_id="other",
                    channel_title="Other",
                    matched_query="repair tutorial",
                    contrast_dimension=ContrastDimension.ACTIVITY,
                    why_this_result="Hands-on",
                )
            ],
        )

    monkeypatch.setattr(
        "app.main.RecommenderService.generate_anti_recommendations",
        fake_generate,
    )

    response = client.post(
        "/api/anti-recommendations",
        json={
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "language": "en",
            "exclude_same_channel": False,
        },
    )
    assert response.status_code == 200
    body = response.text
    assert "test-youtube-key" not in body
    assert "test-gemini-key" not in body


def test_api_invalid_url(client: TestClient) -> None:
    response = client.post(
        "/api/anti-recommendations",
        json={"youtube_url": "https://example.com/video"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_youtube_url"


def test_rate_limit_enforced(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    from app.main import limiter

    def fake_generate(self, request):
        return AntiRecommendationResponse(
            source_video=SourceVideo(
                video_id="dQw4w9WgXcQ",
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                title="Source",
                description="",
                channel_id="channel",
                channel_title="Channel",
                tags=[],
            ),
            source_interpretation="Reading",
            concepts=[
                SearchConcept(
                    query=f"query {index}",
                    contrast_dimension=ContrastDimension.TOPIC,
                    rationale="Why",
                )
                for index in range(3)
            ],
            recommendations=[],
        )

    monkeypatch.setattr(
        "app.main.RecommenderService.generate_anti_recommendations",
        fake_generate,
    )
    limiter.reset()
    payload = {
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "language": "en",
        "exclude_same_channel": False,
    }

    for _ in range(10):
        assert client.post("/api/anti-recommendations", json=payload).status_code == 200

    assert client.post("/api/anti-recommendations", json=payload).status_code == 429
