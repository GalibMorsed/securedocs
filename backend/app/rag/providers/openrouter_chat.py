from collections.abc import Iterator

from openai import APIConnectionError, APIStatusError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

from app.core.config import settings
from app.rag.generation import (
    GenerationChunk,
    GenerationConfigurationError,
    LLMProvider,
    TransientGenerationError,
)


class OpenRouterChatProvider(LLMProvider):
    provider_name = "openrouter"

    def __init__(self, client=None) -> None:
        self.model = settings.chat_model
        key = settings.openrouter_api_key.get_secret_value().strip() if settings.openrouter_api_key else ""
        if client is None and not key:
            raise GenerationConfigurationError("Answer generation is not configured. Set OPENROUTER_API_KEY.")
        self.client = client or OpenAI(
            api_key=key,
            base_url=settings.openrouter_base_url,
            timeout=settings.chat_timeout_seconds,
            max_retries=0,
            default_headers={"X-Title": "SecureDocs"},
        )

    def stream_answer(self, messages: list[dict[str, str]]) -> Iterator[GenerationChunk]:
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                max_tokens=settings.chat_max_output_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
            for part in stream:
                usage = getattr(part, "usage", None)
                if usage is not None:
                    yield GenerationChunk(
                        prompt_tokens=getattr(usage, "prompt_tokens", None),
                        completion_tokens=getattr(usage, "completion_tokens", None),
                    )
                for choice in getattr(part, "choices", []) or []:
                    text = getattr(getattr(choice, "delta", None), "content", None)
                    if isinstance(text, str) and text:
                        yield GenerationChunk(text=text)
        except (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError) as exc:
            raise TransientGenerationError("OpenRouter answer service is temporarily unavailable.") from exc
        except APIStatusError as exc:
            if exc.status_code == 429 or exc.status_code >= 500:
                raise TransientGenerationError("OpenRouter answer service is temporarily unavailable.") from exc
            raise GenerationConfigurationError("OpenRouter rejected the answer request. Check the model and API key.") from exc
