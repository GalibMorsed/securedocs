import math

from openai import APIConnectionError, APIStatusError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

from app.core.config import settings
from app.rag.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingProvider,
    TransientEmbeddingError,
)


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    model = "qwen/qwen3-embedding-8b"
    dimensions = 4096

    def __init__(self, client=None) -> None:
        key = settings.openrouter_api_key.get_secret_value().strip() if settings.openrouter_api_key else ""
        if not client and not key:
            raise EmbeddingConfigurationError("Embedding provider is not configured. Set OPENROUTER_API_KEY.")
        self.client = client or OpenAI(
            api_key=key,
            base_url=settings.openrouter_base_url,
            timeout=settings.embedding_timeout_seconds,
            max_retries=0,
            default_headers={"X-Title": "SecureDocs"},
        )

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self.client.embeddings.create(model=self.model, input=texts)
        except (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError) as exc:
            raise TransientEmbeddingError("OpenRouter embedding service is temporarily unavailable.") from exc
        except APIStatusError as exc:
            if exc.status_code == 429 or exc.status_code >= 500:
                raise TransientEmbeddingError("OpenRouter embedding service is temporarily unavailable.") from exc
            raise EmbeddingConfigurationError("OpenRouter rejected the embedding request. Check the model and API key.") from exc

        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [item.embedding for item in ordered]
        if len(vectors) != len(texts):
            raise EmbeddingConfigurationError("OpenRouter returned an incomplete embedding response.")
        if any(len(vector) != self.dimensions or any(not math.isfinite(value) for value in vector) for vector in vectors):
            raise EmbeddingConfigurationError(f"OpenRouter embeddings must contain exactly {self.dimensions} finite values.")
        return vectors
