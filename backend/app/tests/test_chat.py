from types import SimpleNamespace
from uuid import uuid4

from app.rag.generation import GenerationChunk
from app.schemas.search import SearchResult


def _token(client, email, org):
    response = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "correct horse battery staple",
        "full_name": email.split("@", 1)[0],
        "organization_name": org,
    })
    assert response.status_code == 201
    return response.json()["access_token"]


class FakeLLM:
    provider_name = "openrouter"
    model = "qwen/test-instruct"

    def stream_answer(self, _messages):
        yield GenerationChunk(text="Your policy says to report incidents promptly.")
        yield GenerationChunk(prompt_tokens=100, completion_tokens=12)


def test_chat_streams_grounded_answer_and_persists_verified_citations(auth_client, monkeypatch):
    import app.api.v1.chat as chat_api
    import app.services.chat_service as chat_service

    token = _token(auth_client, "chat-owner@example.com", "Chat Org")
    source = SearchResult(
        document_id=uuid4(), document_name="Incident policy", chunk_id=uuid4(),
        content="Report security incidents promptly to the assigned team.",
        page_number=3, similarity_score=0.82,
    )
    monkeypatch.setattr(chat_api, "get_embedding_provider", lambda: object())
    monkeypatch.setattr(chat_api, "get_llm_provider", FakeLLM)
    monkeypatch.setattr(chat_service, "search_documents", lambda *_args, **_kwargs: [source])
    monkeypatch.setattr(chat_service, "reserve_chat_tokens", lambda *_args: None)

    response = auth_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "How do I report an incident?"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: delta" in response.text
    assert "event: done" in response.text
    assert "Incident policy" in response.text

    with auth_client.app.state.test_session() as db:
        from app.models import Conversation, ConversationMessage
        conversation = db.query(Conversation).one()
        messages = db.query(ConversationMessage).filter_by(conversation_id=conversation.id).order_by(ConversationMessage.created_at).all()
        assert [message.role for message in messages] == ["user", "assistant"]
        assert messages[1].citations[0]["document_name"] == "Incident policy"
        assert messages[1].citations[0]["chunk_id"] == str(source.chunk_id)
        assert messages[1].prompt_tokens == 100
        assert messages[1].model == FakeLLM.model

    outsider = _token(auth_client, "chat-outsider@example.com", "Another Org")
    conversation_id = response.text.split('"conversation_id": "')[1].split('"')[0]
    forbidden = auth_client.get(
        f"/api/v1/chat/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {outsider}"},
    )
    assert forbidden.status_code == 404


def test_chat_returns_no_context_without_calling_llm(auth_client, monkeypatch):
    import app.api.v1.chat as chat_api
    import app.services.chat_service as chat_service

    token = _token(auth_client, "chat-empty@example.com", "Empty Sources Org")
    monkeypatch.setattr(chat_api, "get_embedding_provider", lambda: object())
    monkeypatch.setattr(chat_api, "get_llm_provider", lambda: (_ for _ in ()).throw(AssertionError("LLM must not run without sources")))
    monkeypatch.setattr(chat_service, "search_documents", lambda *_args, **_kwargs: [])

    response = auth_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What is the unknown policy?"},
    )
    assert response.status_code == 200
    assert "event: sources\ndata: {\"citations\": [], \"no_relevant_sources\": true}" in response.text
    assert "I couldn't find relevant information" in response.text


def test_chat_requires_authentication(client):
    assert client.post("/api/v1/chat", json={"question": "What does our policy say?"}).status_code == 401
