from html import unescape
import logging
import re
import time
from urllib.parse import parse_qs, urlparse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import Settings, get_settings
from app.errors import (
    IntegrationUnavailableError,
    InvalidYouTubeUrlError,
    VideoNotFoundError,
    YouTubeQuotaExceededError,
)
from app.models import SearchResultItem, SourceVideo

logger = logging.getLogger(__name__)

VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


class TTLCache:
    """ponytail: in-process dict cache; upgrade to Redis if multi-instance."""

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: object) -> None:
        self._store[key] = (time.monotonic() + self.ttl_seconds, value)


def parse_video_id(url: str) -> str:
    if not url or len(url) > 2048:
        raise InvalidYouTubeUrlError()

    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if host not in YOUTUBE_HOSTS:
        raise InvalidYouTubeUrlError()

    if host.endswith("youtu.be"):
        video_id = parsed.path.lstrip("/").split("/")[0]
        if VIDEO_ID_PATTERN.fullmatch(video_id or ""):
            return video_id
        raise InvalidYouTubeUrlError()

    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        raise InvalidYouTubeUrlError()

    if path_parts[0] in {"watch"}:
        video_id = parse_qs(parsed.query).get("v", [None])[0]
    elif path_parts[0] in {"shorts", "embed", "v", "live"} and len(path_parts) > 1:
        video_id = path_parts[1]
    else:
        raise InvalidYouTubeUrlError()

    if not video_id or not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise InvalidYouTubeUrlError()
    return video_id


def _build_youtube_client(settings: Settings):
    return build(
        "youtube",
        "v3",
        developerKey=settings.youtube_api_key,
        cache_discovery=False,
    )


def _handle_youtube_http_error(error: HttpError) -> None:
    status = error.resp.status if error.resp else None
    if status == 403 and "quota" in str(error).lower():
        raise YouTubeQuotaExceededError() from error
    if status in {500, 502, 503, 504}:
        raise IntegrationUnavailableError("YouTube API is temporarily unavailable.") from error
    raise IntegrationUnavailableError("Unexpected YouTube API error.") from error


def _map_snippet_to_source(video_id: str, snippet: dict) -> SourceVideo:
    return SourceVideo(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=unescape(snippet.get("title", "")).strip(),
        description=unescape(snippet.get("description", "")).strip(),
        channel_id=snippet.get("channelId", ""),
        channel_title=unescape(snippet.get("channelTitle", "")).strip(),
        tags=[unescape(tag) for tag in snippet.get("tags") or []],
        category_id=snippet.get("categoryId"),
    )


def _map_search_item(item: dict, matched_query: str, contrast_dimension, rationale: str) -> SearchResultItem | None:
    video_id = item.get("id", {}).get("videoId")
    snippet = item.get("snippet", {})
    title = unescape(snippet.get("title", "")).strip()
    if not video_id or not title:
        return None

    thumbnails = snippet.get("thumbnails", {})
    thumbnail_url = (
        thumbnails.get("medium", {}).get("url")
        or thumbnails.get("default", {}).get("url")
    )

    return SearchResultItem(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=title,
        description=unescape(snippet.get("description", "")).strip(),
        thumbnail_url=thumbnail_url,
        channel_id=snippet.get("channelId", ""),
        channel_title=unescape(snippet.get("channelTitle", "")).strip(),
        matched_query=matched_query,
        contrast_dimension=contrast_dimension,
        why_this_result=rationale,
    )


class YouTubeService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._cache = TTLCache(self.settings.cache_ttl_seconds)

    def fetch_video_metadata(self, video_id: str) -> SourceVideo:
        cache_key = f"video:{video_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        try:
            client = _build_youtube_client(self.settings)
            response = (
                client.videos()
                .list(part="snippet", id=video_id)
                .execute()
            )
        except HttpError as error:
            _handle_youtube_http_error(error)
        except Exception as error:
            raise IntegrationUnavailableError("Could not reach YouTube API.") from error

        items = response.get("items", [])
        if not items:
            raise VideoNotFoundError()

        source = _map_snippet_to_source(video_id, items[0]["snippet"])
        self._cache.set(cache_key, source)
        return source

    def search_videos(self, query: str, language: str, contrast_dimension, rationale: str) -> list[SearchResultItem]:
        cache_key = f"search:{language}:{query.lower()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        try:
            client = _build_youtube_client(self.settings)
            response = (
                client.search()
                .list(
                    part="snippet",
                    type="video",
                    q=query,
                    maxResults=self.settings.search_results_per_concept,
                    videoDuration="medium",
                    safeSearch="moderate",
                    relevanceLanguage=language,
                )
                .execute()
            )
        except HttpError as error:
            _handle_youtube_http_error(error)
        except Exception as error:
            raise IntegrationUnavailableError("Could not reach YouTube search API.") from error

        results: list[SearchResultItem] = []
        for item in response.get("items", []):
            mapped = _map_search_item(item, query, contrast_dimension, rationale)
            if mapped is not None:
                results.append(mapped)

        self._cache.set(cache_key, results)
        return results
