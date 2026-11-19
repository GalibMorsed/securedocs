from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4_000)
    conversation_id: UUID | None = None
    organization_id: UUID | None = None


class SourceCitation(BaseModel):
    document_id: UUID
    document_name: str
    chunk_id: UUID
    page_number: int | None
    source_text: str
    similarity_score: float


class ConversationSummary(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    citations: list[SourceCitation]
    provider: str | None
    model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    messages: list[ConversationMessageResponse]
