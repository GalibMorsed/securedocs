from abc import ABC, abstractmethod
from dataclasses import dataclass
from collections.abc import Iterator


class GenerationError(Exception):
    """Safe message-generation failure."""


class TransientGenerationError(GenerationError):
    pass


class GenerationConfigurationError(GenerationError):
    pass


@dataclass(frozen=True)
class GenerationChunk:
    text: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMProvider(ABC):
    provider_name: str
    model: str

    @abstractmethod
    def stream_answer(self, messages: list[dict[str, str]]) -> Iterator[GenerationChunk]: ...


def get_llm_provider() -> LLMProvider:
    from app.rag.providers.openrouter_chat import OpenRouterChatProvider

    return OpenRouterChatProvider()
