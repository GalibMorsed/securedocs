import json
import logging
from collections.abc import Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.database import get_db
from app.core.redis import get_redis
from app.models import ConversationMessage, User
from app.rag.embeddings import (
    EmbeddingBudgetExceeded,
    EmbeddingError,
    EmbeddingProvider,
    TransientEmbeddingError,
    get_embedding_provider,
)
from app.rag.generation import GenerationError, LLMProvider, get_llm_provider
from app.schemas.chat import (
    ChatRequest,
    ConversationMessageResponse,
    ConversationResponse,
    ConversationSummary,
)
from app.services import chat_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/conversations", response_model=list[ConversationSummary])
def conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConversationSummary]:
    rows = chat_service.list_conversations(db, current_user)
    return [ConversationSummary.model_validate(row) for row in rows]


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def read_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    conversation = chat_service.get_conversation(db, current_user, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at)
    )
    return ConversationResponse(
        id=conversation.id,
        organization_id=conversation.organization_id,
        title=conversation.title,
        messages=[ConversationMessageResponse.model_validate(message) for message in messages],
    )


@router.post("", status_code=status.HTTP_200_OK, summary="Stream an organization-grounded answer with verified sources")
def create_chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> StreamingResponse:
    try:
        embedding_provider: EmbeddingProvider = get_embedding_provider()
        preparation = chat_service.prepare_chat(db, current_user, payload, embedding_provider, redis_client)
        llm_provider: LLMProvider | None = get_llm_provider() if preparation.citations else None
    except EmbeddingBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (EmbeddingError, GenerationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    def event(name: str, value: object) -> str:
        return f"event: {name}\ndata: {json.dumps(value, ensure_ascii=False, default=str)}\n\n"

    def response_stream() -> Iterator[str]:
        yield event("start", {
            "conversation_id": str(preparation.conversation.id),
            "user_message_id": str(preparation.user_message.id),
        })
        yield event("sources", {
            "citations": [citation.model_dump(mode="json") for citation in preparation.citations],
            "no_relevant_sources": preparation.no_relevant_sources,
        })
        answer_parts: list[str] = []
        prompt_tokens = None
        completion_tokens = None
        try:
            if preparation.no_relevant_sources:
                answer_parts.append(chat_service.NO_RELEVANT_SOURCES_ANSWER)
                yield event("delta", {"text": answer_parts[-1]})
            elif llm_provider is not None:
                for chunk in llm_provider.stream_answer(preparation.messages):
                    if chunk.prompt_tokens is not None:
                        prompt_tokens = chunk.prompt_tokens
                    if chunk.completion_tokens is not None:
                        completion_tokens = chunk.completion_tokens
                    if chunk.text:
                        answer_parts.append(chunk.text)
                        yield event("delta", {"text": chunk.text})

            answer = "".join(answer_parts).strip()
            if not answer:
                answer = "I couldn't produce an answer this time. Please try again."
            assistant_message = chat_service.persist_assistant_message(
                db,
                preparation,
                current_user,
                answer,
                llm_provider,
                prompt_tokens,
                completion_tokens,
            )
            yield event("done", {
                "conversation_id": str(preparation.conversation.id),
                "message_id": str(assistant_message.id),
                "answer": answer,
                "citations": [citation.model_dump(mode="json") for citation in preparation.citations],
                "no_relevant_sources": preparation.no_relevant_sources,
            })
        except GenerationError as exc:
            logger.warning("RAG answer generation failed: %s", exc)
            yield event("error", {"detail": str(exc)})
        except Exception:
            logger.exception("Unexpected error while streaming a grounded answer")
            yield event("error", {"detail": "The answer could not be completed. Please retry."})

    return StreamingResponse(
        response_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
