from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Document, DocumentChunk, OrganizationMember, User
from app.rag.budget import reserve_embedding_tokens
from app.rag.embeddings import EmbeddingProvider
from app.schemas.search import SearchRequest, SearchResult


def search_documents(db: Session, user: User, payload: SearchRequest, provider: EmbeddingProvider, budget_client) -> list[SearchResult]:
    if db.scalar(select(OrganizationMember.id).where(OrganizationMember.user_id == user.id).limit(1)) is None:
        raise PermissionError("You must belong to an organization to search documents")
    from app.rag.token_count import count_tokens

    token_count = count_tokens(payload.query)
    if token_count > settings.embedding_max_query_tokens:
        raise ValueError("Search query exceeds the configured token limit")
    reserve_embedding_tokens(budget_client, token_count)
    query_vector = provider.embed_text(payload.query)
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    statement = (
        select(
            Document.id.label("document_id"),
            Document.name.label("document_name"),
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.content,
            DocumentChunk.page_number,
            (1 - distance).label("similarity_score"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(OrganizationMember, OrganizationMember.organization_id == Document.organization_id)
        .where(
            OrganizationMember.user_id == user.id,
            Document.status == "ready",
            DocumentChunk.embedding_model == settings.embedding_model,
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(payload.top_k)
    )
    if payload.organization_id is not None:
        statement = statement.where(OrganizationMember.organization_id == payload.organization_id)
    return [SearchResult.model_validate(row._mapping) for row in db.execute(statement)]
