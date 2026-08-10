import pytest

from app.errors import InvalidYouTubeUrlError
from app.services.youtube import TTLCache, parse_video_id


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&list=PLtest", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_parse_video_id_accepts_supported_formats(url: str, expected: str) -> None:
    assert parse_video_id(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://example.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/watch?v=bad",
        "https://www.youtube.com/watch",
        "x" * 3000,
    ],
)
def test_parse_video_id_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(InvalidYouTubeUrlError):
        parse_video_id(url)


def test_ttl_cache_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = TTLCache(ttl_seconds=1)
    now = {"value": 100.0}
    monkeypatch.setattr("app.services.youtube.time.monotonic", lambda: now["value"])

    cache.set("key", "value")
    assert cache.get("key") == "value"

    now["value"] = 102.0
    assert cache.get("key") is None


def test_map_source_video_from_api_response() -> None:
    from app.services.youtube import _map_snippet_to_source

    source = _map_snippet_to_source(
        "abc12345678",
        {
            "title": "Test title",
            "description": "",
            "channelId": "channel",
            "channelTitle": "Creator",
            "categoryId": "22",
        },
    )
    assert source.title == "Test title"
    assert source.tags == []
    assert source.category_id == "22"


def test_youtube_api_html_entities_are_decoded() -> None:
    from app.services.youtube import _map_search_item, _map_snippet_to_source

    source = _map_snippet_to_source(
        "abc12345678",
        {"title": "Tokyo&#39;s Best &amp; Brightest", "channelTitle": "Creator&#39;s Channel"},
    )
    result = _map_search_item(
        {
            "id": {"videoId": "def12345678"},
            "snippet": {"title": "Tokyo&#39;s Best &amp; Brightest", "channelTitle": "Creator&#39;s Channel"},
        },
        "query",
        "format",
        "rationale",
    )

    assert source.title == "Tokyo's Best & Brightest"
    assert source.channel_title == "Creator's Channel"
    assert result is not None
    assert result.title == "Tokyo's Best & Brightest"
    assert result.channel_title == "Creator's Channel"


def test_youtube_quota_error_mapping() -> None:
    from googleapiclient.errors import HttpError
    from httplib2 import Response

    from app.errors import YouTubeQuotaExceededError
    from app.services.youtube import _handle_youtube_http_error

    response = Response({"status": "403"})
    error = HttpError(response, b'{"error": {"message": "quotaExceeded"}}')

    with pytest.raises(YouTubeQuotaExceededError):
        _handle_youtube_http_error(error)
