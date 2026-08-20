from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ContrastDimension(str, Enum):
    TOPIC = "topic"
    STANCE = "stance"
    ACTIVITY = "activity"
    FORMAT = "format"
    CONSUMPTION = "consumption"
    TONE = "tone"
    SCALE = "scale"
    PERSPECTIVE = "perspective"


class AntiRecommendationRequest(BaseModel):
    youtube_url: str = Field(max_length=2048)
    language: str = "en"
    exclude_same_channel: bool = False


class SourceVideo(BaseModel):
    video_id: str
    url: str
    title: str
    description: str = ""
    channel_id: str
    channel_title: str
    tags: list[str] = Field(default_factory=list)
    category_id: str | None = None


class SearchConcept(BaseModel):
    query: str = Field(min_length=1)
    contrast_dimension: ContrastDimension
    rationale: str = Field(min_length=1)
    safety_note: str | None = None


class GeminiConceptsResponse(BaseModel):
    source_interpretation: str = Field(min_length=1)
    concepts: list[SearchConcept] = Field(min_length=3, max_length=5)

    @field_validator("concepts")
    @classmethod
    def validate_unique_queries(cls, concepts: list[SearchConcept]) -> list[SearchConcept]:
        queries = [concept.query.strip().lower() for concept in concepts]
        if len(set(queries)) != len(queries):
            raise ValueError("Concept queries must be unique.")
        return concepts


class SearchResultItem(BaseModel):
    video_id: str
    url: str
    title: str
    description: str = ""
    thumbnail_url: str | None = None
    channel_id: str
    channel_title: str
    matched_query: str
    contrast_dimension: ContrastDimension
    why_this_result: str


class AntiRecommendationResponse(BaseModel):
    source_video: SourceVideo
    source_interpretation: str
    concepts: list[SearchConcept]
    recommendations: list[SearchResultItem]
    limited_results_message: str | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
