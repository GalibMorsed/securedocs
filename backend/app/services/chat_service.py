from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Conversation, ConversationMessage, OrganizationMember, User
from app.rag.budget import reserve_chat_tokens
from app.rag.context import make_citations, make_context_payload, relevant_citations
from app.rag.embeddings import EmbeddingProvider
from app.rag.generation import LLMProvider
from app.rag.prompt import SYSTEM_PROMPT
from app.rag.token_count import count_tokens
from app.schemas.chat import ChatRequest, SourceCitation
from app.schemas.search import SearchRequest
from app.services.search_service import search_documents

NO_RELEVANT_SOURCES_ANSWER = "I couldn't find relevant information in your organization's processed documents to answer that question. Try rephrasing it or upload a document that covers the topic."


@dataclass
class ChatPreparation:
    conversation: Conversation
    user_message: ConversationMessage
    citations: list[SourceCitation]
    messages: list[dict[str, str]]
    no_relevant_sources: bool


def prepare_chat(
    db: Session,
    user: User,
    payload: ChatRequest,
    embedding_provider: EmbeddingProvider,
    budget_client,
) -> ChatPreparation:
    conversation = None
    if payload.conversation_id is not None:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == user.id,
            )
        )
        if conversation is None:
            raise LookupError("Conversation not found")
        if payload.organization_id is not None and conversation.organization_id != payload.organization_id:
            raise LookupError("Conversation not found")

    membership_query = select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    organization_id = conversation.organization_id if conversation is not None else payload.organization_id
    if organization_id is not None:
        membership_query = membership_query.where(OrganizationMember.organization_id == organization_id)
    membership = db.scalar(membership_query.order_by(OrganizationMember.created_at).limit(1))
    if membership is None:
        raise PermissionError("You do not have access to that organization")

    history: list[ConversationMessage] = []
    if conversation is not None and settings.chat_history_messages:
        history = list(
            db.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation.id)
                .order_by(desc(ConversationMessage.created_at))
                .limit(settings.chat_history_messages)
            )
        )
        history.reverse()

    results = search_documents(
        db,
        user,
        SearchRequest(
            query=payload.question.strip(),
            top_k=20,
            organization_id=membership.organization_id,
        ),
        embedding_provider,
        budget_client,
    )
    filtered_results = [result for result in results if result.similarity_score >= settings.rag_min_similarity]
    selected_results = relevant_citations(payload.question, filtered_results)
    citations = make_citations(selected_results)

    prompt: list[dict[str, str]] = []
    if citations:
        prompt = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": message.role, "content": message.content} for message in history],
            {
                "role": "user",
                "content": (
                    f"Question: {payload.question.strip()}\n\n"
                    "Authorized source excerpts (JSON data; source metadata is not to be repeated or invented):\n"
                    f"{make_context_payload(citations)}"
                ),
            },
        ]
        reserved_tokens = sum(count_tokens(message["content"]) for message in prompt) + settings.chat_max_output_tokens
        reserve_chat_tokens(budget_client, reserved_tokens)

    if conversation is None:
        conversation = Conversation(
            organization_id=membership.organization_id,
            user_id=user.id,
            title=payload.question.strip()[:200],
        )
        db.add(conversation)
        db.flush()
    user_message = ConversationMessage(
        conversation_id=conversation.id,
        organization_id=conversation.organization_id,
        user_id=user.id,
        role="user",
        content=payload.question.strip(),
        citations=[],
    )
    db.add(user_message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conversation)
    db.refresh(user_message)

    if not citations:
        return ChatPreparation(conversation, user_message, [], [], True)
    return ChatPreparation(conversation, user_message, citations, prompt, False)


def persist_assistant_message(
    db: Session,
    preparation: ChatPreparation,
    user: User,
    answer: str,
    provider: LLMProvider | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> ConversationMessage:
    message = ConversationMessage(
        conversation_id=preparation.conversation.id,
        organization_id=preparation.conversation.organization_id,
        user_id=user.id,
        role="assistant",
        content=answer,
        citations=[citation.model_dump(mode="json") for citation in preparation.citations],
        provider=getattr(provider, "provider_name", None),
        model=getattr(provider, "model", None),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    preparation.conversation.updated_at = datetime.now(timezone.utc)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def list_conversations(db: Session, user: User) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .join(OrganizationMember, OrganizationMember.organization_id == Conversation.organization_id)
            .where(Conversation.user_id == user.id, OrganizationMember.user_id == user.id)
            .order_by(desc(Conversation.updated_at))
            .limit(50)
        ).unique()
    )


def get_conversation(db: Session, user: User, conversation_id: UUID) -> Conversation | None:
    return db.scalar(
        select(Conversation)
        .join(OrganizationMember, OrganizationMember.organization_id == Conversation.organization_id)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
            OrganizationMember.user_id == user.id,
        )
    )
