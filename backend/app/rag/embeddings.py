from abc import ABC, abstractmethod


class EmbeddingError(Exception):
    """Safe, user-displayable embedding failure."""


class TransientEmbeddingError(EmbeddingError):
    """Provider failure that is safe to retry."""


class EmbeddingConfigurationError(EmbeddingError):
    pass


class EmbeddingBudgetExceeded(EmbeddingError):
    pass


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> list[float]: ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


def get_embedding_provider() -> EmbeddingProvider:
    from app.rag.providers.openrouter import OpenRouterEmbeddingProvider

    return OpenRouterEmbeddingProvider()
