from app.models import AntiRecommendationRequest, ContrastDimension, SearchResultItem
from app.services.recommender import RecommenderService, _filter_candidates, _rank_candidates


def _candidate(video_id: str, dimension: ContrastDimension, channel_id: str = "c1") -> SearchResultItem:
    return SearchResultItem(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=f"Title {video_id}",
        description="Desc",
        thumbnail_url=None,
        channel_id=channel_id,
        channel_title="Channel",
        matched_query="query",
        contrast_dimension=dimension,
        why_this_result="Because",
    )


def test_filter_candidates_removes_source_duplicates_and_same_channel() -> None:
    candidates = [
        _candidate("source", ContrastDimension.TOPIC, "source-channel"),
        _candidate("source", ContrastDimension.FORMAT, "other"),
        _candidate("samechan", ContrastDimension.TONE, "source-channel"),
        _candidate("dup", ContrastDimension.ACTIVITY, "other"),
        _candidate("dup", ContrastDimension.FORMAT, "other"),
        _candidate("keep", ContrastDimension.TOPIC, "other"),
    ]

    filtered = _filter_candidates(
        candidates,
        source_video_id="source",
        source_channel_id="source-channel",
        exclude_same_channel=True,
    )
    assert [item.video_id for item in filtered] == ["dup", "keep"]


def test_rank_candidates_prefers_dimension_diversity() -> None:
    candidates = [
        _candidate("a", ContrastDimension.TOPIC),
        _candidate("b", ContrastDimension.TOPIC),
        _candidate("c", ContrastDimension.FORMAT),
        _candidate("d", ContrastDimension.TONE),
    ]
    ranked = _rank_candidates(candidates, results_count=3)
    dimensions = [item.contrast_dimension for item in ranked]
    assert len(set(dimensions)) == 3


def test_generate_anti_recommendations_end_to_end() -> None:
    from app.models import GeminiConceptsResponse, SearchConcept, SourceVideo

    source = SourceVideo(
        video_id="source12345",
        url="https://www.youtube.com/watch?v=source12345",
        title="Source",
        description="Desc",
        channel_id="source-channel",
        channel_title="Source Channel",
        tags=[],
        category_id="22",
    )
    concepts = GeminiConceptsResponse(
        source_interpretation="Reading",
        concepts=[
            SearchConcept(query="repair tutorial", contrast_dimension=ContrastDimension.ACTIVITY, rationale="Hands-on"),
            SearchConcept(query="slow documentary", contrast_dimension=ContrastDimension.FORMAT, rationale="Long-form"),
            SearchConcept(query="budget alternatives", contrast_dimension=ContrastDimension.CONSUMPTION, rationale="Frugal"),
        ],
    )

    class FakeYouTube:
        def fetch_video_metadata(self, video_id: str) -> SourceVideo:
            return source

        def search_videos(self, query, language, contrast_dimension, rationale):
            return [_candidate(f"{contrast_dimension.value}123456", contrast_dimension)]

    class FakeGemini:
        def generate_concepts(self, source_video: SourceVideo) -> GeminiConceptsResponse:
            return concepts

    service = RecommenderService(
        youtube_service=FakeYouTube(),
        gemini_service=FakeGemini(),
    )
    response = service.generate_anti_recommendations(
        AntiRecommendationRequest(
            youtube_url="https://www.youtube.com/watch?v=source12345",
            exclude_same_channel=False,
        )
    )
    assert response.source_video.video_id == "source12345"
    assert len(response.concepts) == 3
    assert len(response.recommendations) == 3
