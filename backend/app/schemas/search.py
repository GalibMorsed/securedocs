from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=8_000)
    top_k: int = Field(default=8, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Query must contain at least two characters")
        return value


class SearchResult(BaseModel):
    document_id: UUID
    document_name: str
    chunk_id: UUID
    content: str
    page_number: int | None
    similarity_score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
