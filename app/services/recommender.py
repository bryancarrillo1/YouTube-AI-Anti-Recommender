from collections import defaultdict

from app.config import Settings, get_settings
from app.models import (
    AntiRecommendationRequest,
    AntiRecommendationResponse,
    SearchResultItem,
)
from app.services.gemini import GeminiService
from app.services.youtube import YouTubeService, parse_video_id


def _filter_candidates(
    candidates: list[SearchResultItem],
    source_video_id: str,
    source_channel_id: str,
    exclude_same_channel: bool,
) -> list[SearchResultItem]:
    seen: set[str] = set()
    filtered: list[SearchResultItem] = []

    for candidate in candidates:
        if candidate.video_id == source_video_id:
            continue
        if exclude_same_channel and candidate.channel_id == source_channel_id:
            continue
        if candidate.video_id in seen:
            continue
        seen.add(candidate.video_id)
        filtered.append(candidate)

    return filtered


def _rank_candidates(candidates: list[SearchResultItem], results_count: int) -> list[SearchResultItem]:
    by_dimension: dict[str, list[SearchResultItem]] = defaultdict(list)
    for candidate in candidates:
        by_dimension[candidate.contrast_dimension.value].append(candidate)

    dimensions = list(by_dimension.keys())
    ranked: list[SearchResultItem] = []
    dim_index = 0

    while len(ranked) < results_count and any(by_dimension[dimension] for dimension in dimensions):
        dimension = dimensions[dim_index % len(dimensions)]
        bucket = by_dimension[dimension]
        if bucket:
            ranked.append(bucket.pop(0))
        dim_index += 1

    return ranked[:results_count]


class RecommenderService:
    def __init__(
        self,
        settings: Settings | None = None,
        youtube_service: YouTubeService | None = None,
        gemini_service: GeminiService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.youtube = youtube_service or YouTubeService(self.settings)
        self.gemini = gemini_service or GeminiService(self.settings)

    def generate_anti_recommendations(self, request: AntiRecommendationRequest) -> AntiRecommendationResponse:
        video_id = parse_video_id(request.youtube_url)
        source_video = self.youtube.fetch_video_metadata(video_id)
        concepts_response = self.gemini.generate_concepts(source_video)

        candidates: list[SearchResultItem] = []
        for concept in concepts_response.concepts:
            search_results = self.youtube.search_videos(
                query=concept.query,
                language=request.language or self.settings.default_language,
                contrast_dimension=concept.contrast_dimension,
                rationale=concept.rationale,
            )
            candidates.extend(search_results)

        filtered = _filter_candidates(
            candidates,
            source_video_id=source_video.video_id,
            source_channel_id=source_video.channel_id,
            exclude_same_channel=request.exclude_same_channel,
        )
        recommendations = _rank_candidates(filtered, self.settings.results_count)

        limited_message = None
        if len(recommendations) < self.settings.results_count:
            limited_message = (
                f"Only {len(recommendations)} suitable result(s) were found for this video."
            )

        return AntiRecommendationResponse(
            source_video=source_video,
            source_interpretation=concepts_response.source_interpretation,
            concepts=concepts_response.concepts,
            recommendations=recommendations,
            limited_results_message=limited_message,
        )
