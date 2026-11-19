from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.rag.embeddings import EmbeddingConfigurationError
from app.rag.providers.openrouter import OpenRouterEmbeddingProvider
from app.schemas.search import SearchRequest
from app.services.search_service import search_documents


def test_openrouter_provider_batches_and_checks_dimensions():
    vectors = [[0.25] * 4096, [0.5] * 4096]
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(data=[
            SimpleNamespace(index=1, embedding=vectors[1]),
            SimpleNamespace(index=0, embedding=vectors[0]),
        ])

    fake_client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    provider = OpenRouterEmbeddingProvider(client=fake_client)
    assert provider.embed_batch(["first", "second"]) == vectors
    assert captured["model"] == "qwen/qwen3-embedding-8b"
    assert captured["input"] == ["first", "second"]

    bad = SimpleNamespace(embeddings=SimpleNamespace(create=lambda **_: SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[1.0])])))
    with pytest.raises(EmbeddingConfigurationError, match="exactly 4096"):
        OpenRouterEmbeddingProvider(client=bad).embed_text("bad")


def test_search_sql_filters_organization_membership_before_vector_results(monkeypatch):
    import app.services.search_service as service

    captured = {}

    class FakeDb:
        def scalar(self, statement):
            return uuid4()

        def execute(self, statement):
            captured["sql"] = str(statement.compile(dialect=postgresql.dialect()))
            return [SimpleNamespace(_mapping={
                "document_id": uuid4(), "document_name": "Policy", "chunk_id": uuid4(),
                "content": "Relevant policy text", "page_number": 2, "similarity_score": 0.91,
            })]

    monkeypatch.setattr(service, "reserve_embedding_tokens", lambda *_: None)
    user = SimpleNamespace(id=uuid4())
    result = search_documents(FakeDb(), user, SearchRequest(query="policy rules"),
        SimpleNamespace(embed_text=lambda _: [0.1] * 4096), object())
    assert result[0].document_name == "Policy"
    sql = captured["sql"].lower()
    assert "organization_members.user_id" in sql
    assert "documents.status =" in sql
    assert "embedding_model" in sql
    assert "<=>" in sql


def test_search_requires_authentication(client):
    response = client.post("/api/v1/search", json={"query": "private policies"})
    assert response.status_code == 401
