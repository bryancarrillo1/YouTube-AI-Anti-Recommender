import json

import pytest
from pydantic import ValidationError

from app.errors import GeminiGenerationFailedError
from app.models import ContrastDimension, GeminiConceptsResponse, SearchConcept
from app.services.gemini import GeminiService, _filter_safe_concepts, _is_unsafe_query


def _valid_response() -> GeminiConceptsResponse:
    concepts = [
        SearchConcept(
            query=f"concept query {index}",
            contrast_dimension=ContrastDimension.TOPIC,
            rationale=f"Rationale {index}",
        )
        for index in range(3)
    ]
    return GeminiConceptsResponse(
        source_interpretation="A cautious reading of the metadata.",
        concepts=concepts,
    )


def test_gemini_schema_rejects_duplicate_queries() -> None:
    concepts = [
        SearchConcept(query="same query", contrast_dimension=ContrastDimension.TOPIC, rationale="One"),
        SearchConcept(query="same query", contrast_dimension=ContrastDimension.FORMAT, rationale="Two"),
        SearchConcept(query="third query", contrast_dimension=ContrastDimension.TONE, rationale="Three"),
    ]
    with pytest.raises(ValidationError):
        GeminiConceptsResponse(source_interpretation="Reading", concepts=concepts)


def test_safety_filter_rejects_unsafe_queries() -> None:
    response = GeminiConceptsResponse(
        source_interpretation="Reading",
        concepts=[
            SearchConcept(query="safe repair tutorial", contrast_dimension=ContrastDimension.ACTIVITY, rationale="A"),
            SearchConcept(query="safe slow living", contrast_dimension=ContrastDimension.TONE, rationale="B"),
            SearchConcept(query="vote for candidate now", contrast_dimension=ContrastDimension.STANCE, rationale="C"),
        ],
    )
    with pytest.raises(GeminiGenerationFailedError):
        _filter_safe_concepts(response)


def test_safety_filter_keeps_valid_concepts() -> None:
    filtered = _filter_safe_concepts(_valid_response())
    assert len(filtered.concepts) == 3


def test_is_unsafe_query_detects_blocked_patterns() -> None:
    assert _is_unsafe_query("how to commit suicide")
    assert not _is_unsafe_query("beginner bicycle repair tutorial")


def test_generate_concepts_retries_on_invalid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    service = GeminiService()
    calls = {"count": 0}

    def fake_generate_raw(source, repair: bool = False) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return "{not-json"
        return json.dumps(_valid_response().model_dump())

    monkeypatch.setattr(service, "_generate_raw", fake_generate_raw)
    result = service.generate_concepts(
        type("Source", (), {
            "title": "Title",
            "description": "Desc",
            "channel_title": "Channel",
            "tags": [],
            "category_id": None,
        })()
    )
    assert calls["count"] == 2
    assert len(result.concepts) == 3
